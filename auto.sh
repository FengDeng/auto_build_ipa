

#cat /Users/DengFeng/.jenkins/jobs/问酷app/workspace/iAsku.xcodeproj/project.pbxproj |while read LINE
#do
#echo $LINE
#done
DIR="$( cd "$( dirname "$0"  )" && pwd  )"

#十七个包得uuid
wk_czhx_uuid="PROVISIONING_PROFILE = \"f0204b59-a108-42c4-b49b-9fec396687b6\";"
wk_czkx_uuid="PROVISIONING_PROFILE = \"0e5276eb-bd94-40b0-8ab6-50595a5cb2df\";"
wk_czsx_uuid="PROVISIONING_PROFILE = \"2ae88585-2a82-4707-bc5a-3dab5d8b871e\";"
wk_czwl_uuid="PROVISIONING_PROFILE = \"153fd41a-9f08-4e17-9240-b7ade48c7f57\";"
wk_czyw_uuid="PROVISIONING_PROFILE = \"7362454b-c40c-46cb-a6d7-4f8694b9bc48\";"
wk_czyy_uuid="PROVISIONING_PROFILE = \"5f6e94c5-fccc-407c-9b40-09bdfdf6acfe\";"
wk_gzdl_uuid="PROVISIONING_PROFILE = \"89598b66-e580-4e10-b439-c152bf2dbfba\";"
wk_gzhx_uuid="PROVISIONING_PROFILE = \"19976627-4bb6-4dbe-9837-c1050fd49676\";"
wk_gzls_uuid="PROVISIONING_PROFILE = \"cd5ef95a-0052-4875-82f9-dd32526387b0\";"
wk_gzsw_uuid="PROVISIONING_PROFILE = \"fcfe5869-3eb2-4dda-a514-f29fd76fa10d\";"
wk_gzsx_uuid="PROVISIONING_PROFILE = \"0d98e212-069b-42fc-a321-2b419ab81d56\";"
wk_gzwl_uuid="PROVISIONING_PROFILE = \"7e8f20c4-c068-4cc2-bd3a-3eb9b75a595d\";"
wk_gzyw_uuid="PROVISIONING_PROFILE = \"38004eda-360d-4e86-9285-3cb89d78813b\";"
wk_gzyy_uuid="PROVISIONING_PROFILE = \"363472bd-36f3-4e5f-a0e5-e86783e5ebf5\";"
wk_gzzz_uuid="PROVISIONING_PROFILE = \"1c7cf5e5-5fa0-4eab-912b-77e0b1cf754a\";"
wk_xxsx_uuid="PROVISIONING_PROFILE = \"5947a8b0-6c98-4270-bcfd-0630b3bbc6b7\";"
wk_xxyw_uuid="PROVISIONING_PROFILE = \"5e9531b5-90f3-410f-a185-a80f83797888\";"

#外部传入的参数
subject=$1
echo $name

if [ ! -n $subject ]; then
echo "lost arg"
exit 1
fi


#定义十七个学科的ProvisionFile
wk_uuid="wk_czhx"

if [ $subject == "wk_czhx" ]
then
wk_uuid=$wk_czhx_uuid
fi
if [ $subject == "wk_czkx" ]
then
wk_uuid=$wk_czkx_uuid
fi
if [ $subject == "wk_czsx" ]
then
wk_uuid=$wk_czsx_uuid
fi
if [ $subject == "wk_czwl" ]
then
wk_uuid=$wk_czwl_uuid
fi
if [ $subject == "wk_czyw" ]
then
wk_uuid=$wk_czyw_uuid
fi
if [ $subject == "wk_czyy" ]
then
wk_uuid=$wk_czyy_uuid
fi
if [ $subject == "wk_gzdl" ]
then
wk_uuid=$wk_gzdl_uuid
fi
if [ $subject == "wk_gzhx" ]
then
wk_uuid=$wk_gzhx_uuid
fi
if [ $subject == "wk_gzls" ]
then
wk_uuid=$wk_gzls_uuid
fi
if [ $subject == "wk_gzsw" ]
then
wk_uuid=$wk_gzsw_uuid
fi
if [ $subject == "wk_gzsx" ]
then
wk_uuid=$wk_gzsx_uuid
fi
if [ $subject == "wk_gzwl" ]
then
wk_uuid=$wk_gzwl_uuid
fi
if [ $subject == "wk_gzyw" ]
then
wk_uuid=$wk_gzyw_uuid
fi
if [ $subject == "wk_gzyy" ]
then
wk_uuid=$wk_gzyy_uuid
fi
if [ $subject == "wk_gzzz" ]
then
wk_uuid=$wk_gzzz_uuid
fi
if [ $subject == "wk_xxsx" ]
then
wk_uuid=$wk_xxsx_uuid
fi
if [ $subject == "wk_xxyw" ]
then
wk_uuid=$wk_xxyw_uuid
fi

#读取工程下project.pbxproj文件 换provision
rex="PROVISIONING_PROFILE.*"
sed -i "" "s?${rex}?$wk_uuid?" ${DIR}/iAsku.xcodeproj/project.pbxproj

#执行python脚本

cd ${DIR}
python build.py -t $subject


#执行打包ipa命令
cocoapods-build $DIR

cd ${DIR}/build/ipa-build/

mv *.ipa ${subject}.ipa

cp ${subject}.ipa /Users/dengfeng/Documents/share/






