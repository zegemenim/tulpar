import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { Stack, router } from 'expo-router';
import * as Notifications from 'expo-notifications';
import { StatusBar } from 'expo-status-bar';
import * as SecureStore from 'expo-secure-store';
import { startActivityAsync } from 'expo-intent-launcher';
import { ayarOku, servisAyariniYaz } from '../lib/api';
import { sesModeliniIndir } from '../lib/guncelleme';
import { bildirimleriBaslat } from '../lib/bildirim';
import { useRenk } from '../lib/tema';

export default function Kok() {
  const r = useRenk();
  const [hazir, setHazir] = useState(false);

  useEffect(() => {
    ayarOku().then((a) => {
      setHazir(true);
      if (!a) router.replace('/kurulum');
      else {
        bildirimleriBaslat().catch(() => {});
        servisAyariniYaz().catch(() => {});
        // Uyandırma ayarı açıksa servisi (yeniden) başlat: güncelleme/yeniden başlatma sonrası Android onu kapatır
        // (model telefonda yoksa önce HP'den iner; kuruluysa hiçbir şey indirmez)
        SecureStore.getItemAsync('uyandirma').then(async (v) => {
          if (v !== 'evet') return;
          await sesModeliniIndir().catch(() => {});  // inemezse servis kendisi internetten dener
          startActivityAsync('android.intent.action.MAIN', {
            packageName: 'dev.tulpar.app', className: 'dev.tulpar.app.UyandirmaActivity', extra: { islem: 'otomatik' },
          }).catch(() => {});
        });
      }
    });
    // bildirime dokununca ilgili ekrana git
    const abone = Notifications.addNotificationResponseReceivedListener((y) => {
      const ekran = y.notification.request.content.data?.ekran as string | undefined;
      if (ekran) router.push(ekran as any);
    });
    return () => abone.remove();
  }, []);

  if (!hazir) {
    return <View style={{ flex: 1, backgroundColor: r.zemin, justifyContent: 'center' }}><ActivityIndicator /></View>;
  }
  return (
    <>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerStyle: { backgroundColor: r.kart }, headerTintColor: r.yazi, contentStyle: { backgroundColor: r.zemin } }}>
        <Stack.Screen name="(sekmeler)" options={{ headerShown: false }} />
        <Stack.Screen name="sohbet/[id]" options={{ title: '' }} />
        <Stack.Screen name="kurulum" options={{ title: 'Sunucuya bağlan' }} />
        <Stack.Screen name="dinle" options={{ headerShown: false }} />
        <Stack.Screen name="sohbetler" options={{ title: 'Geçmiş sohbetler' }} />
        <Stack.Screen name="sesimi-ogren" options={{ title: 'Sesimi öğren' }} />
        <Stack.Screen name="hakkimda" options={{ title: 'Hakkımda (Tulpar ne biliyor)' }} />
      </Stack>
    </>
  );
}
