# Check-in invitați Single Malt · Radisson Blu Brașov (23 octombrie 2026)

Pagină pentru tablete: scrii cel puțin 3 litere din numele invitatului și bifezi **A venit?**. Bifarea apare pe toate tabletele în ~2 secunde. Fără PIN.

- Fiecare invitație arată câte persoane are (coloana B din Excel). La bifare se consideră că au venit toți; cu **− / +** se corectează câți au intrat efectiv.
- Jos se vede mereu câte persoane au venit din total. **Statistici** arată persoanele și invitațiile bifate, plus butonul de ștergere a tuturor bifărilor (confirmare cu `RESET`).
- **Lista completă** (jos, lângă Statistici) arată toți invitații în ordine alfabetică, ca tabel compact (nume în stânga, număr de persoane în dreapta, cei veniți evidențiați), cu filtrele Toți / Au venit / N-au venit și totaluri jos.
- Debifarea cere confirmare. Dacă două tablete bifează aceeași invitație simultan, a doua vede „era deja bifat(ă) de pe altă tabletă”.
- Zoom-ul e dezactivat pe tablete.

## Baza de date

Lista e **statică**: `guests.json`, generat o singură dată din Excel (coloana A = nume, coloana B = număr de invitați):

```bash
python3 import_excel.py "Lista Invitati_SMC_RadissonBrasov_23octombrie2026.xlsx"
```

Antetul și rândul „total” sunt sărite. Numerele de telefon scrise lângă nume sunt eliminate (nu ajung pe tablete), iar textul din paranteze devine un detaliu afișat sub nume. Rezultat: 95 de invitații, 137 de persoane.

Bifările se salvează separat, în `checkins.json` din `DATA_DIR` (discul persistent pe Render), deci rezistă la restart și redeploy.

## Găzduire pe Render

1. **New → Blueprint**, alegi acest repo. `render.yaml` creează serviciul web (plan Starter) cu un disc de 1 GB la `/var/data`.
2. Fiecare push pe `main` face deploy automat.
3. Tabletele deschid adresa serviciului (ex. `https://webui-singlemalt-brasov.onrender.com`).

### Logo

Logo-ul oficial se pune în `static/logo.png`. Dacă lipsește, capul paginii afișează textul „Single Malt”.

## Rulare locală (rezervă)

```bash
python3 server.py
```

Tabletele din aceeași rețea intră pe `http://<IP-laptop>:8080`.
