// tulpar://dinle: uygulama asistan olarak (güç tuşu / sesle) açıldı. Ana ekrana geç ve dinlemeye başla.
import { useEffect } from 'react';
import { router } from 'expo-router';
import { dinlemeIste } from '../lib/dinleIstegi';

export default function Dinle() {
  useEffect(() => {
    dinlemeIste();
    router.replace('/');
  }, []);
  return null;
}
