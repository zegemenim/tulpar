// Telefon bildirimleri: uygulama sunucuyu yoklar (açıkken sık, arka planda ~15 dk'da bir), yeni önemli şeyleri gösterir.
import * as BackgroundTask from 'expo-background-task';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
import * as TaskManager from 'expo-task-manager';
import { istek } from './api';

const GOREV = 'tulpar-yokla';

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

type Yeni = {
  zaman: number;
  onemli: { id: string; sohbet_adi: string; metin: string; eleme: { ozet?: string; aksiyon?: string } }[];
  taslaklar: { id: number; sohbet_adi: string; ozet: string | null }[];
  onaylar: { id: number; baslik: string }[];
};

export async function yokla() {
  const son = Number((await SecureStore.getItemAsync('son_yoklama')) || Date.now() / 1000 - 600);
  const y = await istek<Yeni>(`/bildirimler?sonra=${son}`, undefined, 30000);
  const goster = (title: string, body: string, data: Record<string, unknown>) =>
    Notifications.scheduleNotificationAsync({ content: { title, body, data }, trigger: null });
  for (const o of y.onemli) {
    const uyari = o.eleme.aksiyon === 'uyar';
    await goster(uyari ? `⚠️ ${o.sohbet_adi}` : o.sohbet_adi, o.eleme.ozet || o.metin.slice(0, 120), { ekran: '/' });
  }
  if (y.taslaklar.length === 1) await goster('Taslak hazır', `${y.taslaklar[0].sohbet_adi}: ${y.taslaklar[0].ozet ?? ''}`, { ekran: '/taslaklar' });
  else if (y.taslaklar.length > 1) await goster(`${y.taslaklar.length} taslak hazır`, y.taslaklar.map((t) => t.sohbet_adi).join(', '), { ekran: '/taslaklar' });
  for (const o of y.onaylar) await goster('Onayın bekleniyor', o.baslik, { ekran: '/' });
  await SecureStore.setItemAsync('son_yoklama', String(y.zaman));
}

TaskManager.defineTask(GOREV, async () => {
  try {
    await yokla();
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});

export async function bildirimleriBaslat() {
  await Notifications.requestPermissionsAsync();
  if (!(await TaskManager.isTaskRegisteredAsync(GOREV))) {
    await BackgroundTask.registerTaskAsync(GOREV, { minimumInterval: 15 });
  }
}
