import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { Stack, router } from 'expo-router';
import * as Notifications from 'expo-notifications';
import { StatusBar } from 'expo-status-bar';
import { ayarOku } from '../lib/api';
import { bildirimleriBaslat } from '../lib/bildirim';
import { useRenk } from '../lib/tema';

export default function Kok() {
  const r = useRenk();
  const [hazir, setHazir] = useState(false);

  useEffect(() => {
    ayarOku().then((a) => {
      setHazir(true);
      if (!a) router.replace('/kurulum');
      else bildirimleriBaslat().catch(() => {});
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
