import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Barcode,
  ShieldCheck,
  Search,
  Upload,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Globe,
  ExternalLink,
  Package,
  Layers,
  ArrowRight,
  Sparkles,
  Building2,
  Calendar,
  MapPin,
  FileText,
  Copy,
  Check
} from 'lucide-react';
import { api } from '../services/api';
import Card from '../components/ui/Card';

export default function BarcodeFssaiLookup() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'barcode' | 'fssai'>('barcode');

  // ── Barcode State ──
  const [barcodeInput, setBarcodeInput] = useState('');
  const [barcodeLoading, setBarcodeLoading] = useState(false);
  const [barcodeError, setBarcodeError] = useState<string | null>(null);
  const [barcodeData, setBarcodeData] = useState<any | null>(null);
  const [copied, setCopied] = useState(false);

  // ── FSSAI State ──
  const [fssaiInput, setFssaiInput] = useState('');
  const [fssaiLoading, setFssaiLoading] = useState(false);
  const [fssaiError, setFssaiError] = useState<string | null>(null);
  const [fssaiData, setFssaiData] = useState<any | null>(null);

  // Sample Data Shortcuts
  const sampleBarcodes = [
    { label: 'Coca-Cola (GTIN-13)', code: '5449000000996' },
    { label: 'Indian FMCG (890 Prefix)', code: '8901030383748' },
    { label: 'Tata Tea / Sample EAN', code: '8901058852331' }
  ];

  const sampleFssai = [
    { label: "Haldiram's Central HQ", code: '10014051000910' },
    { label: 'Alpino Health Foods (Delhi)', code: '10716022000249' },
    { label: 'Kissan / HUL (Punjab)', code: '10014063000346' }
  ];

  // ── Handle Barcode Lookup ──
  const handleBarcodeLookup = async (codeToLookup?: string) => {
    const target = (codeToLookup || barcodeInput).trim();
    if (!target) return;
    setBarcodeLoading(true);
    setBarcodeError(null);
    setBarcodeData(null);
    try {
      const res = await api.lookupBarcode(target);
      setBarcodeData(res);
      if (!res.found && !res.is_valid_checksum) {
        setBarcodeError('Barcode format is invalid or not registered in the database.');
      }
    } catch (err: any) {
      setBarcodeError(err.message || 'Failed to fetch product details.');
    } finally {
      setBarcodeLoading(false);
    }
  };

  // ── Handle Barcode Image Scan ──
  const handleImageScan = async (file: File) => {
    setBarcodeLoading(true);
    setBarcodeError(null);
    setBarcodeData(null);
    try {
      const res = await api.scanBarcodeImage(file);
      if (res.detected && res.code) {
        setBarcodeInput(res.code);
        if (res.product_data) {
          setBarcodeData(res.product_data);
        } else {
          // Attempt manual lookup
          await handleBarcodeLookup(res.code);
        }
      } else {
        setBarcodeError('No clear 1D barcode or 2D QR code could be decoded from this image. Please ensure the code is flat and clearly lit.');
      }
    } catch (err: any) {
      setBarcodeError(err.message || 'Image barcode scanning failed.');
    } finally {
      setBarcodeLoading(false);
    }
  };

  // ── Handle FSSAI Verification ──
  const handleFssaiVerify = async (licenceToVerify?: string) => {
    const target = (licenceToVerify || fssaiInput).trim();
    if (!target) return;
    setFssaiLoading(true);
    setFssaiError(null);
    setFssaiData(null);
    try {
      const res = await api.verifyFssaiLicence(target);
      setFssaiData(res);
    } catch (err: any) {
      setFssaiError(err.message || 'Failed to verify FSSAI license.');
    } finally {
      setFssaiLoading(false);
    }
  };

  const handleCopyBarcode = () => {
    if (barcodeData?.barcode) {
      navigator.clipboard.writeText(barcodeData.barcode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* ── Page Header ── */}
      <div className="bg-gradient-to-r from-indigo-950 via-slate-900 to-slate-950 rounded-2xl border border-indigo-500/20 p-6 md:p-8 text-white relative overflow-hidden shadow-xl">
        <div className="absolute right-0 top-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-semibold mb-3 border border-indigo-500/30">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Live Product Intelligence & Regulatory Lookups
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
              Barcode, QR & FSSAI Registry Intelligence
            </h1>
            <p className="text-slate-400 text-sm mt-1 max-w-2xl">
              Scan packaging barcodes or input license numbers to instantly fetch verified statutory declarations, ingredients, nutrition facts, and FoSCoS registration metadata.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('barcode')}
              className={`px-4 py-2.5 rounded-xl font-medium text-sm flex items-center gap-2 transition-all ${
                activeTab === 'barcode'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white border border-slate-700'
              }`}
            >
              <Barcode className="w-4 h-4" />
              Barcode & QR Fetcher
            </button>
            <button
              onClick={() => setActiveTab('fssai')}
              className={`px-4 py-2.5 rounded-xl font-medium text-sm flex items-center gap-2 transition-all ${
                activeTab === 'fssai'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white border border-slate-700'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              FSSAI Licence Decoder
            </button>
          </div>
        </div>
      </div>

      {/* ── TAB 1: BARCODE / QR SCANNER ── */}
      {activeTab === 'barcode' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <Barcode className="w-5 h-5 text-indigo-500" />
              Fetch Product Details from Barcode or QR Code
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
              Enter any global GTIN / EAN barcode number (8 to 14 digits) or upload a photo of the barcode to retrieve verified brand, product name, net quantity, ingredients, and nutrition facts.
            </p>

            {/* Input Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2 flex gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={barcodeInput}
                    onChange={(e) => setBarcodeInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleBarcodeLookup()}
                    placeholder="e.g. 5449000000996 or 8901030383748"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <button
                  onClick={() => handleBarcodeLookup()}
                  disabled={barcodeLoading || !barcodeInput.trim()}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-xl transition flex items-center gap-2 shadow-sm"
                >
                  {barcodeLoading ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Search className="w-4 h-4" />
                  )}
                  Lookup
                </button>
              </div>

              {/* Upload Dropzone */}
              <div>
                <label className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-400 cursor-pointer bg-slate-50 dark:bg-slate-900/50 text-sm text-slate-600 dark:text-slate-400 transition">
                  <Upload className="w-4 h-4 text-indigo-500" />
                  <span>Scan From Photo</span>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleImageScan(e.target.files[0]);
                      }
                    }}
                  />
                </label>
              </div>
            </div>

            {/* Quick Sample Buttons */}
            <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-slate-200 dark:border-slate-800">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1">
                Try Examples:
              </span>
              {sampleBarcodes.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setBarcodeInput(s.code);
                    handleBarcodeLookup(s.code);
                  }}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 dark:hover:text-indigo-400 transition border border-slate-200 dark:border-slate-700"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </Card>

          {/* Error Message */}
          {barcodeError && (
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Lookup Notice</p>
                <p className="mt-0.5 text-xs text-amber-700 dark:text-amber-400">{barcodeError}</p>
              </div>
            </div>
          )}

          {/* Barcode Result Card */}
          {barcodeData && (
            <Card className="p-6 border-indigo-500/30">
              <div className="flex flex-col md:flex-row items-start justify-between gap-6 pb-6 border-b border-slate-200 dark:border-slate-800">
                <div className="flex items-start gap-4">
                  {barcodeData.image_url ? (
                    <img
                      src={barcodeData.image_url}
                      alt={barcodeData.product_name || 'Product'}
                      className="w-24 h-24 object-contain rounded-xl bg-white p-1 border border-slate-200 dark:border-slate-700 shadow-xs"
                    />
                  ) : (
                    <div className="w-24 h-24 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 border border-slate-200 dark:border-slate-700">
                      <Package className="w-10 h-10 stroke-1" />
                    </div>
                  )}
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 flex items-center gap-1">
                        <Barcode className="w-3 h-3" />
                        {barcodeData.barcode}
                      </span>
                      <button
                        onClick={handleCopyBarcode}
                        title="Copy Barcode"
                        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                        barcodeData.is_valid_checksum
                          ? 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400'
                          : 'bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-400'
                      }`}>
                        {barcodeData.is_valid_checksum ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {barcodeData.is_valid_checksum ? 'GS1 Modulo-10 Valid' : 'Invalid Checksum'}
                      </span>
                    </div>

                    <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                      {barcodeData.product_name || 'Unlabeled Packaged Commodity'}
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">
                      Brand: <span className="text-slate-900 dark:text-slate-200">{barcodeData.brand || 'Not Specified'}</span>
                    </p>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <div className="text-right">
                    <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Origin Country</div>
                    <div className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5 justify-end">
                      <Globe className="w-3.5 h-3.5 text-indigo-400" />
                      {barcodeData.origin_country || 'Global / Unknown'} (Prefix {barcodeData.gs1_prefix || '—'})
                    </div>
                  </div>
                  {barcodeData.net_quantity && (
                    <div className="text-right mt-1">
                      <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Declared Net Qty</div>
                      <div className="text-base font-bold text-emerald-600 dark:text-emerald-400">
                        {barcodeData.net_quantity}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Data Grid: Ingredients & Nutrition */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                {/* Ingredients */}
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                  <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-indigo-500" />
                    Ingredients List
                  </h4>
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed max-h-40 overflow-y-auto">
                    {barcodeData.ingredients || 'Ingredients not cataloged in global registry for this barcode.'}
                  </p>
                </div>

                {/* Nutrition Facts */}
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                  <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-500" />
                    Nutrition per 100g / 100ml
                  </h4>
                  {barcodeData.nutrition && Object.keys(barcodeData.nutrition).length > 0 ? (
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="p-2 rounded bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                        <div className="text-slate-400 text-[10px]">Energy</div>
                        <div className="font-bold text-slate-900 dark:text-white">{barcodeData.nutrition.energy_kcal ?? '—'} kcal</div>
                      </div>
                      <div className="p-2 rounded bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                        <div className="text-slate-400 text-[10px]">Protein</div>
                        <div className="font-bold text-slate-900 dark:text-white">{barcodeData.nutrition.proteins_g ?? '—'} g</div>
                      </div>
                      <div className="p-2 rounded bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                        <div className="text-slate-400 text-[10px]">Carbohydrates</div>
                        <div className="font-bold text-slate-900 dark:text-white">{barcodeData.nutrition.carbohydrates_g ?? '—'} g</div>
                      </div>
                      <div className="p-2 rounded bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                        <div className="text-slate-400 text-[10px]">Total Fat</div>
                        <div className="font-bold text-slate-900 dark:text-white">{barcodeData.nutrition.fat_g ?? '—'} g</div>
                      </div>
                      <div className="p-2 rounded bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                        <div className="text-slate-400 text-[10px]">Sugars</div>
                        <div className="font-bold text-slate-900 dark:text-white">{barcodeData.nutrition.sugars_g ?? '—'} g</div>
                      </div>
                      <div className="p-2 rounded bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                        <div className="text-slate-400 text-[10px]">Sodium</div>
                        <div className="font-bold text-slate-900 dark:text-white">{barcodeData.nutrition.sodium_mg ? `${Math.round(barcodeData.nutrition.sodium_mg)} mg` : '—'}</div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 italic">Nutritional facts not cataloged for this product.</p>
                  )}
                </div>
              </div>

              {/* Action Banner */}
              <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  Data source: {barcodeData.provider || 'OpenFoodFacts API & GS1 Prefix Index'}
                </span>
                <button
                  onClick={() => navigate('/analyze')}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 transition"
                >
                  <span>Audit Package Photos for this Product</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ── TAB 2: FSSAI DECODER ── */}
      {activeTab === 'fssai' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-indigo-500" />
              FSSAI 14-Digit Licence Decoder & Verification
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
              Enter any 14-digit FSSAI number to decode the State of Registration, Licensing Category (Central vs. State), Year of Issuance, and FoSCoS format validity.
            </p>

            {/* Input Row */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={fssaiInput}
                  onChange={(e) => setFssaiInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleFssaiVerify()}
                  placeholder="e.g. 10014051000910 or 10716022000249"
                  maxLength={14}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
                />
              </div>
              <button
                onClick={() => handleFssaiVerify()}
                disabled={fssaiLoading || !fssaiInput.trim()}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-xl transition flex items-center gap-2 shadow-sm"
              >
                {fssaiLoading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <ShieldCheck className="w-4 h-4" />
                )}
                Verify Licence
              </button>
            </div>

            {/* Quick Sample Buttons */}
            <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-slate-200 dark:border-slate-800">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1">
                Try Examples:
              </span>
              {sampleFssai.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setFssaiInput(s.code);
                    handleFssaiVerify(s.code);
                  }}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 dark:hover:text-indigo-400 transition border border-slate-200 dark:border-slate-700"
                >
                  {s.label} ({s.code})
                </button>
              ))}
            </div>
          </Card>

          {/* FSSAI Error Message */}
          {fssaiError && (
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Licence Verification Notice</p>
                <p className="mt-0.5 text-xs text-amber-700 dark:text-amber-400">{fssaiError}</p>
              </div>
            </div>
          )}

          {/* FSSAI Result Card */}
          {fssaiData && (
            <Card className="p-6 border-indigo-500/30">
              <div className="flex flex-col md:flex-row items-start justify-between gap-6 pb-6 border-b border-slate-200 dark:border-slate-800">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-mono text-base font-bold px-3 py-1 rounded-lg bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
                      {fssaiData.licence_number}
                    </span>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1 ${
                      fssaiData.status === 'VERIFIED'
                        ? 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400'
                        : fssaiData.status === 'INVALID_FORMAT'
                        ? 'bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-400'
                        : 'bg-sky-100 dark:bg-sky-950/50 text-sky-700 dark:text-sky-400'
                    }`}>
                      {fssaiData.status === 'INVALID_FORMAT' ? <XCircle className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
                      {fssaiData.status === 'INVALID_FORMAT' ? 'Invalid Format' : 'FoSCoS Compliant Format'}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mt-1">
                    {fssaiData.business_name || fssaiData.licence_type || 'Food Business Operator'}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {fssaiData.message}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <a
                    href="https://foscos.fssai.gov.in"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3.5 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 transition flex items-center gap-1.5"
                  >
                    <span>Official FoSCoS Portal</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              {/* Decoded Anatomy */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-slate-400 text-xs flex items-center gap-1.5 mb-1 font-medium">
                    <MapPin className="w-3.5 h-3.5 text-indigo-400" />
                    Jurisdiction / State
                  </div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                    {fssaiData.decoded_state || 'Unknown'}
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    State Code: {fssaiData.state_code || '—'}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-slate-400 text-xs flex items-center gap-1.5 mb-1 font-medium">
                    <Building2 className="w-3.5 h-3.5 text-emerald-400" />
                    Licence Category
                  </div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                    {fssaiData.licence_type || 'Central / State License'}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Category Code: {fssaiData.licence_number ? fssaiData.licence_number[0] : '—'}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-slate-400 text-xs flex items-center gap-1.5 mb-1 font-medium">
                    <Calendar className="w-3.5 h-3.5 text-amber-400" />
                    Year of Registration
                  </div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                    {fssaiData.registration_year || '—'}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Digits 4-5 of sequence
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-slate-400 text-xs flex items-center gap-1.5 mb-1 font-medium">
                    <FileText className="w-3.5 h-3.5 text-sky-400" />
                    FSSAI Logo Rule
                  </div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                    Mandatory on Food
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Rule 2.1.1 (FSSAI 2020)
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
