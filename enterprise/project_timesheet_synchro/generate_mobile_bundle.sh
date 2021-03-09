# The first argument is the platform, i.e. android, ios,...
# The second argument is the app version
#
# Requirements:
# sudo npm install -g cordova
# sudo npm install -g cordova-icon
# sudo apt install xmlstarlet
# sudo apt install imagemagick
#
echo "Creating 'www' bundle for cordova app in directory OdooTimesheets"

./generate_extension.sh

cordova create OdooTimesheets com.odoo.OdooTimesheets OdooTimesheets
cd OdooTimesheets
cordova platform add android --save

[ -d www ] || mkdir www
cp -r ../extension/web www
cp -r ../extension/project_timesheet_synchro www
cp ../extension/timesheet.html www/index.html

cp www/project_timesheet_synchro/static/src/img/icon.png ./

# Setup cordova config.xml
#
app_name='Awesome Timesheet'
app_description='Beautiful time tracking extension to get things done.'
app_author='Odoo S.A.'
app_author_email='help@odoo.com'
app_author_website='https://www.odoo.com/'
app_version=$2 #e.g.: 20

xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -u "/w:widget/w:name" -v "$app_name" config.xml
xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -u "/w:widget/w:description" -v "$app_description" config.xml
xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -u "/w:widget/w:author" -v "$app_author" config.xml
xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -u "/w:widget/w:author/@email" -v "$app_author_email" config.xml
xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -u "/w:widget/w:author/@href" -v "$app_author_website" config.xml
xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -u "/w:widget/@version" -v "0.0.$app_version" config.xml
xmlstarlet edit --inplace -N w=http://www.w3.org/ns/widgets -a "/w:widget" -t 'attr' -n 'android-versionCode' -v "$app_version" config.xml

# Android app configuration
#
cordova prepare android

android_app_path='./platforms/android/app/src/main'
android_app_icon='@drawable/icon'
android_app_theme='@android:style/Theme.Black.NoTitleBar'

# Add icon
#
mkdir $android_app_path/res/drawable-mdpi
cp ./icon.png $android_app_path/res/drawable-mdpi

# Setup AndroidManifest
#
xmlstarlet edit --inplace -u "/manifest/application/@android:icon" -v "$android_app_icon" $android_app_path/AndroidManifest.xml
xmlstarlet edit --inplace -u "/manifest/application/activity/@android:theme" -v $android_app_theme $android_app_path/AndroidManifest.xml
# Add <uses-feature android:name="android.hardware.wifi" />
xmlstarlet edit --inplace -a "/manifest/supports-screens" -t 'elem' -n 'uses-feature' $android_app_path/AndroidManifest.xml
xmlstarlet edit --inplace -a "/manifest/uses-feature[not(@android:name)]" -t 'attr' -n 'android:name' -v 'android.hardware.wifi' $android_app_path/AndroidManifest.xml
# Add <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
xmlstarlet edit --inplace -a "/manifest/uses-feature[@android:name='android.hardware.wifi']" -t 'elem' -n 'uses-permission' $android_app_path/AndroidManifest.xml
xmlstarlet edit --inplace -a "/manifest/uses-permission[not(@android:name)]" -t 'attr' -n 'android:name' -v 'android.permission.ACCESS_NETWORK_STATE' $android_app_path/AndroidManifest.xml
# Add <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
xmlstarlet edit --inplace -a "/manifest/uses-permission[@android:name='android.permission.ACCESS_NETWORK_STATE']" -t 'elem' -n 'uses-permission' $android_app_path/AndroidManifest.xml
xmlstarlet edit --inplace -a "/manifest/uses-permission[not(@android:name)]" -t 'attr' -n 'android:name' -v 'android.permission.ACCESS_WIFI_STATE' $android_app_path/AndroidManifest.xml

# iOS app configuration
#
if [ $1 = "ios" ]
then
    cordova platform remove android
    cordova platform add ios --save
    cp www/project_timesheet_synchro/static/src/img/icon246.png ./
    cordova-icon --config=config.xml --icon=icon246.png
    cordova plugin add https://github.com/katzer/cordova-plugin-hidden-statusbar-overlay
    cordova prepare ios
fi
