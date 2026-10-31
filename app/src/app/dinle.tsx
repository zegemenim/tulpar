// tulpar://dinle: uygulama asistan olarak (güç tuşu / sesle) açıldı. Ana ekrana geç ve dinlemeye başla.
// Uygulama zaten açıksa var olan ana ekrana dönülür: replace('/') yığına YENİ bir ana ekran koyuyordu; dinlemeyi
// arkada kalan eski ekran başlatıyor, görünen yeni ekran "Konuşmak için bas"ta kalıyordu.
import { useEffect } from 'react';
import { router } from 'expo-router';
import { dinlemeIste } from '../lib/dinleIstegi';

export default function Dinle() {
  useEffect(() => {
    dinlemeIste();
    if (router.canDismiss()) router.dismissTo('/');
    else router.replace('/');
  }, []);
  return null;
}
