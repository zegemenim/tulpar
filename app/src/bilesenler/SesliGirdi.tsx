// Her yazı alanının yanında mikrofon: konuş, yazıya dönüşsün, istersen düzelt. Uygulamanın her yerinde aynı.
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSesleYaz } from '../lib/ses';
import { useRenk } from '../lib/tema';

type Ozellik = Omit<TextInputProps, 'onChangeText' | 'value'> & { value: string; onChangeText: (m: string) => void };

export default function SesliGirdi({ value, onChangeText, style, multiline, ...diger }: Ozellik) {
  const r = useRenk();
  // söylenen, mevcut yazının sonuna eklenir (yazdığın silinmez)
  const ses = useSesleYaz((m) => onChangeText(value ? `${value.trimEnd()} ${m}` : m));
  const dinliyor = ses.durum === 'dinliyor';
  return (
    <View>
      <View style={s.satir}>
        <TextInput value={value} onChangeText={onChangeText} multiline={multiline} placeholderTextColor={r.soluk}
          style={[s.girdi, { color: r.yazi, borderColor: dinliyor ? r.kirmizi : r.cizgi, backgroundColor: r.zemin },
            multiline && { minHeight: 80, textAlignVertical: 'top' }, style]} {...diger} />
        <Pressable onPress={ses.dokun} accessibilityLabel="Sesle yaz"
          style={[s.mik, { backgroundColor: dinliyor ? r.kirmizi : r.ana }]}>
          {ses.durum === 'yaziya' ? <ActivityIndicator color="#fff" />
            : <Ionicons name={dinliyor ? 'stop' : 'mic'} size={20} color="#fff" />}
        </Pressable>
      </View>
      {dinliyor ? <Text style={{ color: r.kirmizi, fontSize: 12, marginTop: 4 }}>Dinliyorum… bitince tekrar bas</Text> : null}
      {ses.hata ? <Text style={{ color: r.kirmizi, fontSize: 12, marginTop: 4 }}>{ses.hata}</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  satir: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  girdi: { flex: 1, borderWidth: 1, borderRadius: 10, padding: 10, fontSize: 15 },
  mik: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
});
