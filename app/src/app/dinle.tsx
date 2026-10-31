// tulpar://dinle: uygulama asistan olarak (güç tuşu / sesle) açıldı. Ana ekrana geç ve dinlemeye başla.
import { useEffect } from 'react';
import { router } from 'expo-router';

export default function Dinle() {
  useEffect(() => {
    router.replace({ pathname: '/', params: { dinle: String(Date.now()) } });
  }, []);
  return null;
}
