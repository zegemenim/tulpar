import { ColorValue } from 'react-native';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useRenk } from '../../lib/tema';
import { usePano } from '../../lib/pano';

type Ad = keyof typeof Ionicons.glyphMap;
const ikon = (ad: Ad) => ({ color, size }: { color: ColorValue; size: number }) => <Ionicons name={ad} color={color as string} size={size} />;

export default function Sekmeler() {
  const r = useRenk();
  usePano();
  return (
    <Tabs screenOptions={{
      headerStyle: { backgroundColor: r.kart }, headerTintColor: r.yazi,
      tabBarStyle: { backgroundColor: r.kart, borderTopColor: r.cizgi },
      tabBarActiveTintColor: r.ana, tabBarInactiveTintColor: r.soluk,
    }}>
      <Tabs.Screen name="index" options={{ title: 'Tulpar', tabBarLabel: 'Ana', tabBarIcon: ikon('mic-circle') }} />
      <Tabs.Screen name="whatsapp" options={{ title: 'WhatsApp', tabBarIcon: ikon('chatbubbles') }} />
      <Tabs.Screen name="taslaklar" options={{ title: 'Taslaklar', tabBarIcon: ikon('create') }} />
      <Tabs.Screen name="gorevler" options={{ title: 'Görevler', tabBarIcon: ikon('checkbox') }} />
      <Tabs.Screen name="cihazlar" options={{ title: 'Cihazlar', tabBarIcon: ikon('phone-portrait') }} />
      <Tabs.Screen name="bilgisayar" options={{ title: 'Bilgisayar', tabBarIcon: ikon('desktop') }} />
      <Tabs.Screen name="ayarlar" options={{ title: 'Ayarlar', tabBarIcon: ikon('settings') }} />
    </Tabs>
  );
}
