# !/usr/bin/python
#coding=utf-8

import subprocess
import re
import os,sys
from ftplib import FTP 
try:
    import yaml
except ImportError:
    sys.exit('\033[31munable to import yaml module, please do "sudo pip install pyyaml" or "sudo easy_install pyyaml"\033[0m')
import glob
import argparse
from StringIO import StringIO
import urllib,httplib
import types
import zipfile
import time
import shutil


null_file = open('/dev/null','w')
PlistBuddy = '/usr/libexec/PlistBuddy'
__version__ = '1.0.20150711'

APP_ID_NAME_KEY = 'AppIDName'
CREATION_DATE_KEY = 'CreationDate'
APPLICATION_IDENTIFIER_KEY = 'application-identifier'
EXPIRATION_DATE_KEY = 'ExpirationDate'
NAME_KEY = 'Name'
TEAM_NAME_KEY = 'TeamName'

PROVISION_BASE_INFO_KEY = (
    APP_ID_NAME_KEY,
    CREATION_DATE_KEY,
    APPLICATION_IDENTIFIER_KEY,
    EXPIRATION_DATE_KEY,
    NAME_KEY,
    TEAM_NAME_KEY
)

info_key_re = re.compile(r'''\s*<key>([\w\d\.-]+)</key>\s*''')
info_value_re = re.compile(r'''\s*<(string|date)>(.+)</\1>\s*''', re.IGNORECASE)

console_color_re = re.compile(r'(\033\[([\d;]+)m|\r)', re.IGNORECASE);
rfc1034identifier_re = re.compile(r'[^0-9a-z-]', re.IGNORECASE | re.UNICODE)
bundle_id_in_provision_re = re.compile(r'^[0-9a-z]+\.', re.IGNORECASE)


def sucess_string_builder(string):
    return '\033[32m%s\033[0m' % string

def error_string_builder(string):
    return '\033[31m%s\033[0m' % string

def wrarning_string_builder(string):
    return '\033[33m%s\033[0m' % string

def rfc1034identifier(string):
    return rfc1034identifier_re.sub('-', string)



class BuildApp(object):
    def __init__(self, configuration,build_type):
        
        if subprocess.call(['type','xcodebuild'],stdout = subprocess.PIPE,stderr=subprocess.PIPE) != 0:
            sys.exit(error_string_builder('please install commond line tools'))

        self.configuration = configuration
        self.build_type = build_type
        self.sdk = None
        self.targets = []
        self.schemes = []
        self.build_configurations = []
        self.scheme = None
        self.build_dir = None
        self.plist_path = None
        self.product_name = None
        self.verbose = True
        self.bundle_id = None
        self.packaged_bundle_id = None
        self.original_bundle_id = None
        self.app_version = None
        self.build_version = None
        self.basic_info = {}
        self.bundle_id_in_provision = None

        self.current_upload = None
        self.current_total_uploaded = 0
        self.current_total_size = 0
        self.stdout_str_len = 0

        self.is_xctool_installed = subprocess.call(['type', 'xctool'], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0


    #检测证书的有效性#
    def detecting_basic_info_with_provision_file(self,file):

        basic_info = {}
        provision_info_key = None
        found_key = False
        with open(file,'r') as pf:
            for provison_line in pf:
                match = info_key_re.match(provison_line)
                if match:
                    matchedkey = match.group(1)
                    if matchedkey in PROVISION_BASE_INFO_KEY:
                        provision_info_key = matchedkey
                        found_key = True
                        continue
                if found_key == True:
                    match = info_value_re.match(provison_line)
                    if match:
                        matchedvalue = match.group(2)
                        if provision_info_key == EXPIRATION_DATE_KEY:
                            expriration_date = time.strptime(matchedvalue,"%Y-%m-%dT%H:%M:%SZ")
                            now = time.gmtime()
                            if expriration_date < now:
                                raise Exception(error_string_builder('The mobileprovision file was expired'))

                        basic_info[provision_info_key] = matchedvalue
                        found_key = False

        if not self.bundle_id:
            self.detecting_app_info()

        self.bundle_id_in_provision = bundle_id_in_provision_re.sub('',basic_info[APPLICATION_IDENTIFIER_KEY])
        self.basic_info = basic_info


    #校验证书签名的有效性#
    def check_codesign_for_name(self,codesign_name):
        valid_codesigns = subprocess.Popen(['security','find-identity','-p','codesigning','-v'],stdout=subprocess.PIPE)
        valid_codesigns.wait()
        greped_codesign = subprocess.Popen(['grep','-o',codesign_name],stdin=valid_codesigns.stdout,stdout=null_file)
        greped_codesign.wait()
        return greped_codesign.returncode == 0

        #检查项目编译相关的一些配置信息
    def detecting_basic_build_info(self):
        cmd = ['xcodebuild','-showBuildSettings']
        cmd.extend(['-configuration',self.configuration['configuration']])

        if self.configuration.has_key('workspace'):
            cmd.extend(['-workspace',self.configuration['workspace']])
            if not self.configuration.has_key('scheme'):
                if not self.schemes:
                    print(success_string_builder('detecting targets, build configurations and schemes...'))
                    build_app.detect_schemes_configurations_and_targets()
                cmd.extend(['-scheme',self.schemes[0]])
            else:
                cmd.extend(['-scheme',self.configuration['scheme']])
        elif self.configuration.has_key('project'):
            cmd.extend(['-project',self.configuration['project']])
            if self.configuration.has_key('target'):
                cmd.extend(['-target',self.configuration['target']])

        output = subprocess.check_output(cmd,stderr=null_file)
        build_dir_re = re.compile('\s*BUILT_PRODUCTS_DIR\s*=\s*(.+)\s*')
        self.build_dir = build_dir_re.findall(output)[0]
        product_name_re = re.compile('\s*PRODUCT_NAME\s*=\s*(.+)\s*')
        self.product_name = product_name_re.findall(output)[0]
        plist_path_re = re.compile('\s*INFOPLIST_FILE\s*=\s*(.+)\s*')
        self.plist_path = plist_path_re.findall(output)[0]
        sdk_name_re = re.compile('\s*SDK_NAME\s*=\s*(.+)\s*')
        self.sdk = sdk_name_re.findall(output)[0]



    #检查项目中的schemes tartgets
    def detect_schemes_configurations_and_targets(self):
        cmd = ['xcodebuild','-list']
        if self.configuration.has_key('workspace'):
            cmd.extend(['-workspace',self.configuration['workspace']])
        elif self.configuration.has_key('project'):
                cmd.extend(['-project',self.configuration['project']])

        scheme_re = re.compile(r'\s*Scheme:\s*')
        target_re = re.compile(r'\s*Targets:\s*')
        build_configurations_re = re.compile(r'\s*Build Configuration:\s*')
        output = subprocess.check_output(cmd,stderr = null_file)

        ofp = StringIO(output)
        should_append = False
        current_attribute = None

        for line in ofp:
            stripped_line = line.strip()
            if  not should_append:
                if scheme_re.match(stripped_line):
                    should_append = True
                    current_attribute = 'schemes'
                elif target_re.match(stripped_line):
                    should_append = True
                    current_attribute = 'targets'
                elif build_configurations_re.match(stripped_line):
                    should_append = True
                    current_attribute = 'build_configurations'
            else:
                if not stripped_line:
                    should_append = False
                    current_attribute = None
                else:
                    if current_attribute == 'schemes':
                        self.schemes.append(stripped_line)
                    elif current_attribute =='targets':
                        self.targets.append(stripped_line)
                    elif current_attribute == 'build_configurations':
                        self.build_configurations.append(stripped_line)

        ofp.close()
        if self.schemes:
            self.scheme = self.schemes[0]

    #从项目中plist文件中读取相关的配置#
    def get_info_from_plist(self,plist_path,key):
        cmd_arguments = [PlistBuddy ,'-c',"Print :%s" %key,plist_path]
        output = subprocess.check_output(cmd_arguments)
        return output.strip()

     #设置plist文件中的相关配置#
    def set_info_for_plist(self,plist_path,key,value):
        cmd_arguments = [PlistBuddy ,'-c',"Set :%s %s" % (key,value),plist_path]
        return_code = subprocess.check_call(cmd_arguments)
        return return_code

    #检查项目plist配置#
    def detecting_app_info(self):
        if not self.plist_path:
            raise Exception(error_string_builder('No plist file found'))
        info_dict = {
            'bundle_id':'CFBundleIdentifier',
            'build_version':'CFBundleVersion',
            'app_version':'CFBundleShortVersionString'
        }

        for key in info_dict:
            value = self.get_info_from_plist(self.plist_path,info_dict[key])
            if key == 'bundle_id':
                self.original_bundle_id = value
            if value.find('${PRODUCT_NAME:rfc1034identifier}') != -1:
                value = value.replace('${PRODUCT_NAME:rfc1034identifier}',rfc1034identifier(self.product_name.rstrip('.app')))
            if key:
                setattr(self,key,value)

    #项目的clean#
    def clean(self):
        build_arguments = []
        build_arguments.extend(['-sdk',self.sdk])
        build_arguments.extend(['-configuration',self.configuration['configuration']])

        if self.configuration.has_key('workspace'):
            build_arguments.extend(['-workspace',self.configuration['workspace']])
            if self.configuration.has_key('scheme'):
                build_arguments.extend(['-scheme',self.configuration['scheme']])
            else:
                build_arguments.extend(['-scheme',self.scheme])
        elif self.configuration.has_key('project'):
            build_arguments.extend(['-project',self.configuration['project']])
            if self.configuration.has_key('target'):
                cmd.extend(['-target',self.configuration['target']])

        if self.configuration.has_key('build_dir'):
            build_arguments.extend(['BUILT_PRODUCTS_DIR=%s' %self.configuration['build_dir']])
        
        build_arguments.append('clean')

        try:
            xctool_arguments = ['xctool']
            xctool_arguments.extend(build_arguments)
            xctool_cmd = subprocess.Popen(xctool_arguments)
            xctool_cmd.wait()
        except OSError:
            xcodebuild_arguments = ['xcodebuild']
            xcodebuild_arguments.extend(build_arguments)
            xcodebuild_cmd = subprocess.Popen(xcodebuild_arguments)
            xcodebuild_cmd.wait()

    #项目的编译#
    def build(self):
        build_arguments = []
        build_arguments.extend(['-sdk',self.sdk])
        build_arguments.extend(['-configuration',self.configuration['configuration']])
        if self.configuration.has_key('workspace'):
            build_arguments.extend(["-workspace",self.configuration['workspace']])
            if self.configuration.has_key('scheme'):
                build_arguments.extend(['-scheme',self.configuration['scheme']])
            else:
                build_arguments.extend(['-scheme',self.scheme])
        elif self.configuration.has_key('project'):
            build_arguments.extend(['-project',self.configuration['project']])
            if self.configuration.has_key('target'):
                cmd.extend(['-target',self.configuration['target']])
            
        if self.configuration.has_key('build_dir'):
            build_arguments.extend(['BUILT_PRODUCTS_DIR=%s' % self.configuration['build_dir']])
            if not os.path.isdir(self.configuration['build_dir']):
                os.makedirs(self.configuration['build_dir'])
        else:
            if not os.path.isdir(self.build_dir):
                os.makedirs(self.build_dir)

        self.packaged_bundle_id = self.bundle_id


        
        if self.configuration.has_key('overwrite_and_recover_bundle_id') and self.configuration['overwrite_and_recover_bundle_id'] is True:
            if self.configuration.has_key('bundle_id'):
                if self.basic_info[APPLICATION_IDENTIFIER_KEY].find(self.configuration['bundle_id']) == -1:
                    sys.exit(error_string_builder('The bunlde identifier does not match provision file'))
                self.set_info_for_plist(self.plist_path, 'CFBundleIdentifier', self.configuration['bundle_id'])
                self.packaged_bundle_id = self.configuration['bundle_id']
            else:
                self.set_info_for_plist(self.plist_path, 'CFBundleIdentifier', self.bundle_id_in_provision)
                self.packaged_bundle_id = self.bundle_id_in_provision

        return_code = 1

        if self.is_xctool_installed:
            xctool_build_args = ['script', '-q', '/dev/null', 'xctool']
            if not self.verbose:
                if self.configuration.has_key('report_file'):
                    xctool_build_cmd.extend(['-reporter', 'pretty:%s' % (self.configuration['report_file'], )])
            xctool_build_args.extend(build_arguments)
            xctool_build_args.extend(['build'])
            pipe = subprocess.PIPE if self.verbose else None
            xctool_cmd = subprocess.Popen(xctool_build_args, stdout=pipe, stderr=pipe);

            if self.verbose:
                report_file = None
                if self.configuration.has_key('report_file'):
                    report_file = open(self.configuration['report_file'], 'w')
                while xctool_cmd.poll() is None:
                    output = xctool_cmd.stdout.readline()
                    if output:
                        print output
                        if report_file:
                            report_file.write(console_color_re.sub('', output))
                if report_file:
                    report_file.close()
                comunicate_stderr = xctool_cmd.stderr.read()
                if comunicate_stderr:
                    print(comunicate_stderr)
            return_code = xctool_cmd.returncode
            sys.exit(sucess_string_builder(return_code))
        else:
            xcbuild_args = ['script', '-q', '/dev/null', 'xcodebuild']
            if self.verbose:
                xcbuild_args.extend(['-verbose'])
            xcbuild_args.extend(build_arguments)
            xcbuild_args.extend(['build'])
            xcbuild_cmd = subprocess.Popen(xcbuild_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            report_file = None
            if self.configuration.has_key('report_file'):
                report_file = open(self.configuration['report_file'], 'w')
            while xcbuild_cmd.poll() is None:
                output = xcbuild_cmd.stdout.readline()
                if self.verbose:
                    print output
                if report_file and output:
                    report_file.write(console_color_re.sub('', output))
            if report_file:
                report_file.close()
            comunicate_stderr = xcbuild_cmd.stderr.read()
            if comunicate_stderr:
                print(comunicate_stderr)
            return_code = xcbuild_cmd.returncode


        if self.configuration.has_key('overwrite_and_recover_bundle_id') and self.configuration['overwrite_and_recover_bundle_id'] is True:
            self.set_info_for_plist(self.plist_path,'CFBundleIdentifier',self.original_bundle_id)
            
        if return_code == 0:
            build_dir = self.configuration['build_dir'] if self.configuration.has_key('build_dir') else self.build_dir
            app_path = os.path.join(build_dir,self.product_name)
                
            if self.configuration.has_key('icon_dir'):
                try:
                    if os.path.isdir(self.configuration['icon_dir']):
                        icon_dir = os.path.abspath(self.configuration['icon_dir'])
                        icons = glob.glob(os.path.join(icon_dir,'*.png'))
                        for icon in icons:
                            shutil.copy(icon,app_path)
                except IOError as e:
                    print('%s NOT FOUND!' % self.configuration['icon_dir'])

            tips = 'packaging ipa...'
            sys.stdout.write(sucess_string_builder(tips))
            sys.stdout.flush()
            ipa_path = self.sign_app_to_ipa(self.configuration['bundle_id'])
            sys.stdout.write('\r' + ' ' * len(tips))
            sys.stdout.flush()
            print(sucess_string_builder('\rPackaging ipa OK!'))

        else:
            sys.exit(sucess_string_builder('BUILD FAILED!'))

    #压缩编译文件#
    def zipDSYM(self,dsym_path,zipPath):
        current_path = os.path.abspath(os.curdir)
        zipFile = zipfile.ZipFile(zipPath, 'w', zipfile.ZIP_DEFLATED)
        dsym_dir = os.path.dirname(dsym_path)
        os.chdir(dsym_dir)
        dsym_basename = os.path.basename(dsym_path)
        for dir_path,dirnames,filenames in os.walk(dsym_basename):
            for filename in filenames:
                fullpath = os.path.join(dir_path,filename)
                zipFile.write(fullpath)
        zipFile.close()
        os.chdir(current_path)

    #更新项目的AppIcon#
    def updateAppIcon(self,provision_dir = None):
        to_path = './iAsku/Images.xcassets/AppIcon.appiconset/' #App_Icon的文件夹
        frome_path = provision_dir + 'App_icon/'

        if os.path.exists(to_path):
            print(sucess_string_builder("AppIcon 文件夹存在"))
        else:
            error_string_builder("AppIcon 文件夹不存在")

        if os.path.exists(frome_path):
            print(sucess_string_builder("配置文件中AppIcon文件夹存在"))
        else:
            sys.exit(error_string_builder("配置文件中AppIcon文件夹存在"))

        original =  glob.glob(os.path.join(to_path,'*.png'))
        for icon in original:
            os.remove(icon)

        form = glob.glob(os.path.join(frome_path,'*.png'))
        for icon in form:
            destination = to_path + icon.split("/")[-1]
            shutil.copyfile(icon,destination)


     #更新项目中HomePageList 文件
    def updateHomePageImageList(self,provision_dir = None):
        to_path = './iAsku/Config' #项目的config文件
        frome_path = provision_dir + 'Config'

        if os.path.exists(to_path):
            print(sucess_string_builder("Config 文件夹存在"))
        else:
            error_string_builder("Config 文件夹不存在")

        if os.path.exists(frome_path):
            print(sucess_string_builder("配置文件中Config文件夹存在"))
        else:
            sys.exit(error_string_builder("配置文件中Config文件夹存在"))

        shutil.rmtree(to_path,True)
        shutil.copytree(frome_path,to_path)


    #生成ipad包#
    def sign_app_to_ipa(self,bundle_id):
        ipa_path = self.configuration['ipa_dir']
        print (sucess_string_builder(ipa_path))
        if not os.path.isdir(ipa_path):
            os.makedirs(ipa_path)

        bundle_id = self.packaged_bundle_id
        version = self.app_version
        build_version = self.build_version
        full_ipa_path = os.path.join(ipa_path, '%s_%s.ipa' % ('' if not bundle_id else bundle_id + '.', build_version))
        full_ipa_path = os.path.abspath(full_ipa_path)
        build_dir = self.configuration['build_dir'] if self.configuration.has_key('build_dir') else self.build_dir
        app_path = os.path.join(build_dir, self.product_name)
        sign_cmd_arguments = ['xcrun', '-sdk', self.sdk, 'PackageApplication']
        sign_cmd_arguments.extend([app_path])
        sign_cmd_arguments.extend(['-o', full_ipa_path])
        sign_cmd_arguments.extend(['--sign', self.basic_info[TEAM_NAME_KEY]])
        #sign_cmd_arguments.extend(['--embed', os.path.abspath(self.configuration['provision_dir']+self.configuration['provision_file'])])
        subprocess.check_call(sign_cmd_arguments)
        return full_ipa_path
        

if __name__ == '__main__':
    
    configuration = {
    'configuration':'Release',
    'report_file':'xcodebuild_output',
    'verbose':True,
    }

    try:
        confi_path = os.path.split(os.path.realpath(__file__))[0] + '/.xcbuild-app.yml'
        config_fp = open(confi_path)
    except IOError:
        sys.exit(error_string_builder('configuration file not found'))

    yaml_configuration = yaml.safe_load(config_fp)
    if yaml_configuration:
        configuration.update(yaml_configuration)
    config_fp.close()

    if configuration.has_key('build_type'):
        build_types = configuration['build_type'].keys()
    else:
        build_types = ['AppleStore']
    if not configuration.has_key('workspace'):
        workspaces = glob.glob('*.xcworkspace') #glob模块是用来查找匹配的文件的#
        if len(workspaces) > 1:
            raise Exception(error_string_builder('mutiple workspaces detected, please specify one'))
        else:
            if len(workspaces) > 0:
                configuration['workspace'] = workspaces[0]  #检测到项目中的workSpace#

    if not configuration.has_key('project'):
        projects = glob.glob('*.xcodeproj')#glob模块是用来查找匹配的文件的#
        print projects
        if len(projects) >1:
            raise Exception(error_string_builder('mutiple workspace detected ,please specify one'))
        else:
            configuration['project'] = projects[0] #检测到项目中的project#

    parser = argparse.ArgumentParser()  #生成ArgumentParser命令行解析工具实例#
    parser.add_argument('-w', '--workspace', dest='workspace', help='workspace path', default=configuration['workspace'])
    parser.add_argument('-p', '--project', dest='project', help='project path', default=configuration['project'])
    parser.add_argument('-o', '--open_after_build', dest='open_after_build', action='store_true', default=False, help='open IPAs directory after build')
    parser.add_argument('-v', '--verbose', action='store_true', default=True, dest='verbose', help='show build details')
    parser.add_argument('-t', '--build_type', choices=build_types, default=build_types[0], help='what type of app you want to build')
    parser.add_argument('-c', '--clean_before_build', action='store_true', default=True, dest='clean_before_build', help='do clean action before build')
    args = parser.parse_args()

    configuration.update(configuration['build_type'][args.build_type])
    configuration.update(vars(args))

    configuration['ipa_dir']= './build/IPAs/%s/' % args.build_type
    build_app = BuildApp(configuration,args.build_type) #编译App#
    build_app.verbose = args.verbose

    build_app.updateAppIcon(build_app.configuration['provision_dir'])
    build_app.updateHomePageImageList(build_app.configuration['provision_dir'])

    sys.stdout.write(sucess_string_builder('detecting targets, build configurations and schemes...'))
    sys.stdout.flush()
    build_app.detect_schemes_configurations_and_targets()
    print(sucess_string_builder(u'\r✔︎ detecting targets, build configurations and schemes...'))

    sys.stdout.write(sucess_string_builder('detecting build basic info...'))
    sys.stdout.flush()
    build_app.detecting_basic_build_info()
    print(sucess_string_builder(u'\r✔︎ detecting build basic info...'))

    #检查plist文件中app相关信息
    sys.stdout.write(sucess_string_builder('detecting app basic info from plist file...'))
    sys.stdout.flush()
    build_app.detecting_app_info()
    print(sucess_string_builder(u'\r✔︎ detecting app basic information from plist file...'))

    #检查证书的有效性
    sys.stdout.write(sucess_string_builder('detecting information from provision file...'))
    sys.stdout.flush()
    build_app.detecting_basic_info_with_provision_file(configuration['provision_dir'] + configuration['provision_file'])
    print(sucess_string_builder(u'\r✔︎ detecting information from provision file...'))

    #检查项目中的签名信息
    sys.stdout.write(sucess_string_builder('checking codesign certificate...'))
    sys.stdout.flush()
    build_app.check_codesign_for_name(build_app.basic_info[TEAM_NAME_KEY])
    print(sucess_string_builder(u'\r✔︎ checking codesign certificate...'))

    if args.clean_before_build:
         build_app.clean()
         time.sleep(2)

    build_app.build()




    