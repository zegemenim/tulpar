// Tulpar WhatsApp köprüsü (Baileys: tarayıcısız, doğrudan WhatsApp protokolü).
// - Hariç tutulan sohbetler BURADA elenir; içerikleri Tulpar'a hiç ulaşmaz.
// - Sahibi hariç tutma listesini onaylayana kadar hiçbir mesaj Tulpar'a iletilmez.
// - Okundu bilgisi gönderilmez, çevrimiçi görünmez (bildirimler telefona gelmeye devam eder).
// - Kendiliğinden mesaj göndermez; sadece Tulpar'ın /gonder isteğiyle (sahibin onayından sonra).
import makeWASocket, { Browsers, DisconnectReason, downloadMediaMessage, getContentType, isJidGroup, jidNormalizedUser, useMultiFileAuthState } from 'baileys';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const VERI = path.join(os.homedir(), 'tulpar/veri');
const ANAHTAR = fs.readFileSync(path.join(VERI, 'anahtar'), 'utf8').trim();
const HARIC_YOL = path.join(VERI, 'haric.json');
const HARIC_ONAY = path.join(VERI, 'haric-onaylandi');
const ADLAR_YOL = path.join(VERI, 'wa-adlar.json');          // sadece sohbet adları
const GECMIS_HAM = path.join(VERI, 'wa-gecmis-bekleyen.jsonl'); // onaydan önce gelen geçmiş; onaydan sonra süzülüp silinir
const TULPAR = 'http://127.0.0.1:8090';
// sahibin adı (repoda değil): ~/tulpar/veri/sahip.json
let SAHIP = 'Kullanıcı';
try { SAHIP = JSON.parse(fs.readFileSync(path.join(VERI, 'sahip.json'), 'utf8')).ad || SAHIP; } catch (_) {}

const log = (m) => { try { execFileSync('logger', ['-t', 'tulpar', m]); } catch (_) {} console.log(m); };
const onayli = () => fs.existsSync(HARIC_ONAY);
const bekle = (ms) => new Promise((r) => setTimeout(r, ms));

let adlar = {};
try { adlar = JSON.parse(fs.readFileSync(ADLAR_YOL, 'utf8')); } catch (_) {}
let adKaydiZamanlayici = null;
function adKaydet(jid, ad, grup) {
  if (!jid || jid === 'status@broadcast' || !ad) return;
  if (adlar[jid]?.ad === ad) return;
  adlar[jid] = { ad, grup: !!grup };
  clearTimeout(adKaydiZamanlayici);
  adKaydiZamanlayici = setTimeout(sohbetListesiYaz, 3000);
}
function sohbetListesiYaz() {
  fs.writeFileSync(ADLAR_YOL, JSON.stringify(adlar));
  const satirlar = Object.entries(adlar).map(([jid, a], i) => `${i + 1}\t${a.grup ? 'grup' : 'kisi'}\t${a.ad}\t${jid}`);
  fs.writeFileSync(path.join(VERI, 'sohbet-listesi.txt'), satirlar.join('\n') + '\n');
}
const ad = (jid) => adlar[jid]?.ad || jid.split('@')[0];

function haricMi(jid) {
  let h;
  try { h = JSON.parse(fs.readFileSync(HARIC_YOL, 'utf8')).sohbetler || []; } catch (_) { h = []; }
  const s = new Set(h.map((x) => x.toLocaleLowerCase('tr')));
  return s.has(jid.toLocaleLowerCase('tr')) || s.has(ad(jid).toLocaleLowerCase('tr'));
}

function tulparaGonder(veri) {
  return new Promise((ok) => {
    const govde = Buffer.from(JSON.stringify(veri));
    const r = http.request(TULPAR + '/mesaj', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': govde.length, 'x-tulpar-anahtar': ANAHTAR },
    }, (y) => { y.resume(); y.on('end', ok); });
    r.on('error', (e) => { log(`HATA Tulpar'a iletilemedi: ${e.message}`); ok(); });
    r.end(govde);
  });
}

let sock = null;
let benim = new Set();  // kendi jid ve lid'im

function metinCikar(m) {
  const tur = getContentType(m);
  if (!tur) return { metin: '', baglam: null };
  const icerik = m[tur];
  if (tur === 'conversation') return { metin: icerik, baglam: null };
  const etiket = { audioMessage: 'sesli mesaj', imageMessage: 'fotoğraf', videoMessage: 'video', documentMessage: 'belge',
    stickerMessage: 'çıkartma', locationMessage: 'konum', contactMessage: 'kişi kartı', pollCreationMessage: 'anket' }[tur];
  const yazi = icerik?.text || icerik?.caption || icerik?.name || '';
  return { metin: etiket ? `[${etiket}]${yazi ? ' ' + yazi : ''}` : yazi, baglam: icerik?.contextInfo || null };
}

function donustur(msg, gecmis = false) {
  const jid = msg.key.remoteJid;
  if (!jid || jid === 'status@broadcast' || !msg.message) return null;
  let { metin, baglam } = metinCikar(msg.message);
  if (!metin) return null;
  const grup = isJidGroup(jid);
  const benden = !!msg.key.fromMe;
  const etiketlendim = (baglam?.mentionedJid || []).some((j) => benim.has(jidNormalizedUser(j)));
  for (const b of benim) metin = metin.replaceAll('@' + b.split('@')[0], '@' + SAHIP);
  if (etiketlendim && !metin.includes('@' + SAHIP)) metin = '@' + SAHIP + ' ' + metin;
  const alintiBenden = baglam?.participant && benim.has(jidNormalizedUser(baglam.participant));
  if (grup && !benden && alintiBenden) metin = "(sahibin mesajına cevap) " + metin;
  if (!grup && !benden && msg.pushName) adKaydet(jid, adlar[jid]?.ad || msg.pushName, false);
  return {
    id: msg.key.id, kaynak: 'whatsapp', sohbet_id: jid, sohbet_adi: ad(jid), grup,
    gonderen_id: benden ? 'ben' : (msg.key.participant || jid), gonderen_adi: benden ? SAHIP : (grup ? msg.pushName || '?' : ad(jid)),
    benden, metin, alinti_id: baglam?.stanzaId || null, zaman: Number(msg.messageTimestamp) || Date.now() / 1000, gecmis,
  };
}

// Geçmiş: hariç tutma onaylandıysa doğrudan (hariç tutulanlar elenerek) Tulpar'a gider; onaydan önce gelen
// kısım diskte bekler, onaydan sonra süzülüp gönderilir ve ham dosya silinir. Medya indirilmez, sadece metin.
let gecmisSayac = 0;
async function gecmisGonder(mesajlar) {
  for (const m of mesajlar) {
    if (haricMi(m.sohbet_id)) continue;
    m.sohbet_adi = ad(m.sohbet_id);
    await tulparaGonder(m);
    if (++gecmisSayac % 2000 === 0) log(`WhatsApp gecmisi aliniyor: ${gecmisSayac} mesaj`);
  }
}

async function bekleyenGecmisiIsle() {
  if (!fs.existsSync(GECMIS_HAM)) return;
  while (!onayli()) await bekle(10000);
  const satirlar = fs.readFileSync(GECMIS_HAM, 'utf8').split('\n').filter(Boolean).map((s) => JSON.parse(s));
  await gecmisGonder(satirlar);
  fs.unlinkSync(GECMIS_HAM);  // hariç tutulanlar dahil ham geçmiş tamamen silinir
  log(`WhatsApp bekleyen gecmis islendi: ${satirlar.length} satir`);
}

async function baglan() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(VERI, 'wa-oturum-baileys'));
  sock = makeWASocket({
    auth: state, logger: pino({ level: 'silent' }), browser: Browsers.ubuntu('Desktop'),  // masaüstü kimliği: WhatsApp tam geçmişi buna gönderir
    markOnlineOnConnect: false, syncFullHistory: true,
  });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      fs.writeFileSync(path.join(VERI, 'wa-qr.txt'), qr);
      qrcode.generate(qr, { small: true });
      log('WhatsApp QR hazir: Mac terminalinde tulpar-qr');
    }
    if (connection === 'open') {
      try { fs.unlinkSync(path.join(VERI, 'wa-qr.txt')); } catch (_) {}
      benim = new Set([sock.user.id, sock.user.lid].filter(Boolean).map(jidNormalizedUser));
      log('WhatsApp bagli' + (onayli() ? '' : ' (haric listesi onaylanana kadar hicbir mesaj okunmuyor)'));
      try {
        const gruplar = await sock.groupFetchAllParticipating();
        for (const [jid, g] of Object.entries(gruplar)) adKaydet(jid, g.subject, true);
      } catch (e) { log(`HATA grup adlari: ${e.message}`); }
      sohbetListesiYaz();
      log(`WhatsApp sohbet listesi: ${Object.keys(adlar).length} sohbet`);
      bekleyenGecmisiIsle().catch((e) => log(`HATA gecmis: ${e.message}`));
    }
    if (connection === 'close') {
      const kod = lastDisconnect?.error?.output?.statusCode;
      if (kod === DisconnectReason.loggedOut) {
        log('WhatsApp oturumu kapatildi (telefondan cikis): yeniden QR gerekiyor');
        fs.rmSync(path.join(VERI, 'wa-oturum-baileys'), { recursive: true, force: true });
        process.exit(1);
      }
      log(`WhatsApp baglantisi koptu (${kod}), yeniden baglaniliyor`);
      await bekle(5000);
      baglan();
    }
  });
  sock.ev.on('contacts.upsert', (kisiler) => { for (const k of kisiler) adKaydet(k.id, k.name || k.notify, false); });
  sock.ev.on('chats.upsert', (sohbetler) => { for (const c of sohbetler) adKaydet(c.id, c.name, isJidGroup(c.id)); });
  sock.ev.on('messaging-history.set', async ({ chats, contacts, messages, isLatest, progress }) => {
    for (const k of contacts || []) adKaydet(k.id, k.name || k.notify, false);
    for (const c of chats || []) adKaydet(c.id, c.name, isJidGroup(c.id));
    const donusen = (messages || []).map((m) => donustur(m, true)).filter(Boolean);
    if (!onayli()) {
      if (donusen.length) fs.appendFileSync(GECMIS_HAM, donusen.map((m) => JSON.stringify(m)).join('\n') + '\n', { mode: 0o600 });
    } else {
      await gecmisGonder(donusen);
    }
    log(`WhatsApp gecmis parcasi: ${donusen.length} mesaj${progress != null ? `, %${progress}` : ''}${isLatest ? ' (son)' : ''}`);
  });
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' && type !== 'append') return;
    for (const msg of messages) {
      // teşhis için sadece tür bilgisi (içerik yok): hangi mesaj neden işlenmedi görülsün
      const jid = msg.key.remoteJid || '';
      const neden = !onayli() ? 'onaysiz' : haricMi(jid) ? 'haric' : !msg.message ? 'icerik-yok(sifre cozulemedi?)' : 'islendi';
      log(`wa olay: ${type} ${jid.split('@')[1] || '?'} ${getContentType(msg.message || {}) || '-'} ${msg.key.fromMe ? 'benden' : 'gelen'} -> ${neden}`);
      try {
        if (!onayli() || haricMi(msg.key.remoteJid || '')) continue;  // içerik hiçbir yere gitmez
        const m = donustur(msg);
        if (m && getContentType(msg.message) === 'audioMessage') {  // sesli mesaj: HP'de yazıya dökülecek
          try {
            const sesKlasor = path.join(VERI, 'ses');
            fs.mkdirSync(sesKlasor, { recursive: true, mode: 0o700 });
            m.ses_dosyasi = path.join(sesKlasor, `${m.id}.ogg`);
            fs.writeFileSync(m.ses_dosyasi, await downloadMediaMessage(msg, 'buffer', {}), { mode: 0o600 });
          } catch (e) { log(`HATA ses indirme: ${e.message}`); delete m.ses_dosyasi; }
        }
        if (m) await tulparaGonder(m);
      } catch (e) { log(`HATA mesaj isleme: ${e.message}`); }
    }
  });
}

// Gönderim: sadece HP içinden, anahtarla. sahibin onayladığı taslaklar Tulpar üzerinden gelir.
http.createServer((istek, yanit) => {
  const bitir = (kod, v) => { yanit.writeHead(kod, { 'Content-Type': 'application/json' }); yanit.end(JSON.stringify(v)); };
  if (istek.method !== 'POST' || istek.url !== '/gonder') return bitir(404, { hata: 'yok' });
  if (istek.headers['x-tulpar-anahtar'] !== ANAHTAR) return bitir(401, { hata: 'anahtar' });
  let govde = '';
  istek.on('data', (p) => { govde += p; });
  istek.on('end', async () => {
    try {
      const { sohbet_id, metin, alinti } = JSON.parse(govde);
      if (haricMi(sohbet_id)) return bitir(403, { hata: 'hariç tutulan sohbet' });
      const secenek = {};
      if (alinti?.id) {  // alıntılanacak mesaj: Tulpar'ın hafızasındaki bilgilerle
        secenek.quoted = {
          key: { remoteJid: sohbet_id, id: alinti.id, fromMe: !!alinti.benden,
            participant: isJidGroup(sohbet_id) && !alinti.benden ? alinti.gonderen_id : undefined },
          message: { conversation: alinti.metin || '' },
        };
      }
      const m = await sock.sendMessage(sohbet_id, { text: metin }, secenek);
      log(`WhatsApp gonderildi: ${ad(sohbet_id)}`);
      bitir(200, { id: m?.key?.id });
    } catch (e) { log(`HATA gonderim: ${e.message}`); bitir(500, { hata: e.message }); }
  });
}).listen(8099, '127.0.0.1');

process.on('unhandledRejection', (e) => log(`HATA kopru: ${e && e.message}`));
baglan();
