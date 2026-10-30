import { useColorScheme } from 'react-native';

const acik = {
  zemin: '#F5F6F8', kart: '#FFFFFF', yazi: '#14181F', soluk: '#6B7280', cizgi: '#E5E7EB',
  ana: '#1F4FD8', anaYazi: '#FFFFFF', yesil: '#16A34A', kirmizi: '#DC2626', sari: '#D97706',
  balonBen: '#DCF8C6', balonO: '#FFFFFF', alinti: '#EEF2F7',
};
const koyu: typeof acik = {
  zemin: '#0E1116', kart: '#171B22', yazi: '#E8EAED', soluk: '#9AA3AF', cizgi: '#262C36',
  ana: '#5B8CFF', anaYazi: '#0E1116', yesil: '#22C55E', kirmizi: '#F87171', sari: '#FBBF24',
  balonBen: '#1F3B2D', balonO: '#1E242D', alinti: '#252C37',
};

export type Renkler = typeof acik;
export const useRenk = (): Renkler => (useColorScheme() === 'dark' ? koyu : acik);
