// Android'de Tulpar'ı "dijital asistan" olarak seçilebilir yapar: güç/ana ekran tuşuna basılı tutunca açılır.
const { withAndroidManifest } = require('expo/config-plugins');

module.exports = function asistan(config) {
  return withAndroidManifest(config, (c) => {
    const app = c.modResults.manifest.application[0];
    const ana = app.activity.find((a) => a.$['android:name'] === '.MainActivity');
    ana['intent-filter'] = ana['intent-filter'] || [];
    const varMi = ana['intent-filter'].some((f) => (f.action || []).some((x) => x.$['android:name'] === 'android.intent.action.ASSIST'));
    if (!varMi) {
      ana['intent-filter'].push({
        action: [{ $: { 'android:name': 'android.intent.action.ASSIST' } }, { $: { 'android:name': 'android.intent.action.VOICE_COMMAND' } }],
        category: [{ $: { 'android:name': 'android.intent.category.DEFAULT' } }],
      });
    }
    return c;
  });
};
