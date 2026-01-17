# 技術実装方法

## 技術スタック

### 推奨構成

```
フレームワーク: Next.js (App Router)
スタイリング: Tailwind CSS
フォーム: Formspree（無料プランで月50件まで）
ホスティング: Vercel（おまかせプラン）/ 静的HTML（スタンダードプラン）
バージョン管理: Git / GitHub
```

### なぜこの構成？

**Next.js**:
- モダンでプロフェッショナルな見た目
- 静的HTMLへのエクスポートが簡単
- 開発効率が高い
- 後からの拡張性が高い

**Tailwind CSS**:
- デザインの一貫性
- 高速な開発
- カスタマイズが容易
- ファイルサイズが小さい

**Formspree**:
- サーバーサイド不要
- 無料プランあり
- 簡単に実装できる
- 顧客のメールアドレスに直接送信

---

## プロジェクト構成

### ディレクトリ構造

```
corporate-site-template/
├── app/
│   ├── page.tsx                 # トップページ
│   ├── layout.tsx               # 共通レイアウト
│   ├── globals.css              # グローバルスタイル
│   ├── contact/
│   │   └── page.tsx             # 問い合わせページ
│   └── privacy/
│       └── page.tsx             # プライバシーポリシー
├── components/
│   ├── Header.tsx               # ヘッダー
│   ├── Footer.tsx               # フッター
│   ├── Hero.tsx                 # ヒーローセクション
│   ├── CompanyInfo.tsx          # 会社概要
│   ├── BusinessInfo.tsx         # 事業内容
│   └── ContactForm.tsx          # 問い合わせフォーム
├── config/
│   └── company-data.json        # 顧客情報（ここだけ編集）
├── public/
│   ├── favicon.ico
│   └── images/
├── styles/
│   ├── theme-a.css              # テーマA（ミニマル）
│   ├── theme-b.css              # テーマB（コーポレート）
│   └── theme-c.css              # テーマC（モダン）
├── next.config.js               # Next.js設定
├── tailwind.config.js           # Tailwind設定
├── package.json
└── README.md
```

### 顧客情報の管理

```json
// config/company-data.json
{
  "companyName": "株式会社サンプル",
  "representative": "山田太郎",
  "address": "東京都渋谷区1-2-3 サンプルビル4F",
  "established": "2024年1月15日",
  "capital": "100万円",
  "business": "Webサービスの企画・開発・運営",
  "description": "私たちは最新のテクノロジーを活用し、お客様のビジネスを加速させるソリューションを提供します。",
  "email": "info@example.com",
  "phone": "03-1234-5678",
  "theme": "a",
  "formspreeId": "YOUR_FORM_ID"
}
```

このファイルを編集するだけで全ページに反映される。

---

## Next.js 設定

### next.config.js

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',  // 静的HTMLエクスポート
  images: {
    unoptimized: true,  // 画像最適化を無効化
  },
  trailingSlash: true,  // URLの末尾にスラッシュ
}

module.exports = nextConfig
```

### package.json

```json
{
  "name": "corporate-site-template",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "export": "next build",
    "package": "npm run build && cd out && zip -r ../site.zip . && cd .."
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.2.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.3.6",
    "typescript": "^5.3.0"
  }
}
```

---

## Tailwind CSS 設定

### tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0066FF',
          600: '#0052CC',
          700: '#0047B3',
          900: '#001a44',
        }
      },
      fontFamily: {
        sans: ['Noto Sans JP', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 10px 40px rgba(0, 0, 0, 0.08)',
        'card': '0 2px 8px rgba(0, 0, 0, 0.12)',
      }
    }
  },
  plugins: [],
}
```

---

## コンポーネント実装例

### Hero セクション

```tsx
// components/Hero.tsx
import companyData from '@/config/company-data.json'

export default function Hero() {
  return (
    <section className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center px-6">
        <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
          {companyData.companyName}
        </h1>
        <p className="text-xl md:text-2xl text-gray-600 mb-8 max-w-2xl mx-auto">
          {companyData.description}
        </p>
        <a
          href="#contact"
          className="inline-block bg-blue-600 text-white px-8 py-4 rounded-lg
                     hover:bg-blue-700 transform hover:-translate-y-1
                     transition-all shadow-lg font-semibold"
        >
          お問い合わせ
        </a>
      </div>
    </section>
  )
}
```

### 会社概要セクション

```tsx
// components/CompanyInfo.tsx
import companyData from '@/config/company-data.json'

export default function CompanyInfo() {
  return (
    <section id="company" className="py-20 bg-white">
      <div className="max-w-6xl mx-auto px-6">
        <h2 className="text-3xl font-bold text-center mb-12 text-gray-900">
          会社概要
        </h2>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-gray-50 p-8 rounded-2xl shadow-md hover:shadow-xl transition-shadow">
            <dl className="space-y-4">
              <div>
                <dt className="text-sm text-gray-500 mb-1">会社名</dt>
                <dd className="text-lg font-semibold">{companyData.companyName}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500 mb-1">代表者</dt>
                <dd className="text-lg font-semibold">{companyData.representative}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500 mb-1">設立</dt>
                <dd className="text-lg font-semibold">{companyData.established}</dd>
              </div>
            </dl>
          </div>

          <div className="bg-gray-50 p-8 rounded-2xl shadow-md hover:shadow-xl transition-shadow">
            <dl className="space-y-4">
              <div>
                <dt className="text-sm text-gray-500 mb-1">所在地</dt>
                <dd className="text-lg">{companyData.address}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500 mb-1">資本金</dt>
                <dd className="text-lg">{companyData.capital}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500 mb-1">事業内容</dt>
                <dd className="text-lg">{companyData.business}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </section>
  )
}
```

### 問い合わせフォーム

```tsx
// components/ContactForm.tsx
'use client'

import companyData from '@/config/company-data.json'

export default function ContactForm() {
  return (
    <section id="contact" className="py-20 bg-gradient-to-br from-gray-50 to-blue-50">
      <div className="max-w-2xl mx-auto px-6">
        <h2 className="text-3xl font-bold text-center mb-12 text-gray-900">
          お問い合わせ
        </h2>

        <form
          action={`https://formspree.io/f/${companyData.formspreeId}`}
          method="POST"
          className="bg-white p-8 rounded-2xl shadow-xl"
        >
          <div className="mb-6">
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
              会社名・お名前 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="name"
              id="name"
              required
              className="w-full px-4 py-3 border border-gray-300 rounded-lg
                         focus:ring-2 focus:ring-blue-500 focus:border-transparent
                         transition-all"
            />
          </div>

          <div className="mb-6">
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              メールアドレス <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              name="email"
              id="email"
              required
              className="w-full px-4 py-3 border border-gray-300 rounded-lg
                         focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div className="mb-6">
            <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-2">
              お問い合わせ内容 <span className="text-red-500">*</span>
            </label>
            <textarea
              name="message"
              id="message"
              rows={6}
              required
              className="w-full px-4 py-3 border border-gray-300 rounded-lg
                         focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <input type="hidden" name="_replyto" value={companyData.email} />

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-4 rounded-lg font-semibold
                       hover:bg-blue-700 transform hover:-translate-y-1
                       transition-all shadow-lg"
          >
            送信する
          </button>
        </form>
      </div>
    </section>
  )
}
```

---

## デザインテーマ

### テーマA: ミニマル・クリーン

```css
/* styles/theme-a.css */
:root {
  --color-bg: #FFFFFF;
  --color-text: #1a1a1a;
  --color-accent: #0066FF;
  --color-border: #E5E7EB;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: 'Noto Sans JP', sans-serif;
  font-weight: 300;
}

h1, h2, h3 {
  font-weight: 700;
  letter-spacing: 0.05em;
}
```

### テーマB: コーポレート

```css
/* styles/theme-b.css */
:root {
  --color-bg: #F8F9FA;
  --color-primary: #2C3E50;
  --color-accent: #3498DB;
  --color-light: #ECF0F1;
}

body {
  background-color: var(--color-bg);
  color: var(--color-primary);
  font-family: 'Zen Kaku Gothic New', sans-serif;
}
```

### テーマC: モダン・スタイリッシュ

```css
/* styles/theme-c.css */
:root {
  --color-bg: #0f0f0f;
  --color-text: #f5f5f5;
  --color-accent: #00d4ff;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: 'Inter', 'Noto Sans JP', sans-serif;
}
```

---

## ビルド・エクスポート

### 開発環境での確認

```bash
# 開発サーバー起動
npm run dev

# http://localhost:3000 でプレビュー
```

### 静的HTMLのビルド（スタンダードプラン）

```bash
# ビルド
npm run build

# outフォルダに静的ファイル生成
ls out/
# 404.html
# index.html
# _next/
# contact/
# privacy/

# ZIP化
npm run package
# → site.zip が生成される
```

### Vercelへのデプロイ（おまかせプラン）

```bash
# Vercel CLIをインストール（初回のみ）
npm install -g vercel

# ログイン（初回のみ）
vercel login

# デプロイ
vercel --prod

# カスタムドメイン追加
vercel domains add example.com

# DNS情報確認
vercel domains inspect example.com
```

---

## 問い合わせフォームの設定

### Formspreeの設定手順

1. **Formspreeアカウント作成**
   - https://formspree.io/ にアクセス
   - Sign Upでアカウント作成（無料）

2. **新しいフォーム作成**
   - 「New Form」をクリック
   - フォーム名を入力（例: 株式会社サンプル 問い合わせ）
   - Form IDをコピー（例: `mxxxyyyy`）

3. **company-data.jsonに設定**
   ```json
   {
     "formspreeId": "mxxxyyyy"
   }
   ```

4. **受信先メールアドレス設定**
   - FormspreeのSettings
   - Email通知を顧客のメールアドレスに設定

### 代替案: Googleフォーム

```tsx
// 埋め込み用
<iframe
  src="https://docs.google.com/forms/d/e/xxxxx/viewform?embedded=true"
  width="100%"
  height="800"
  frameBorder="0"
>
  読み込んでいます…
</iframe>
```

---

## 効率化のための自動化

### CLIツールの作成（将来的に）

```bash
# 自作CLIで顧客情報を入力
npx create-corporate-site

# 対話式で情報入力
? 会社名: 株式会社サンプル
? 代表者: 山田太郎
? 所在地: 東京都...
? テーマ: (A) ミニマル / (B) コーポレート / (C) モダン

# 自動で生成・デプロイ
```

---

## トラブルシューティング

### ビルドエラー

**エラー**: `Image optimization using Next.js' default loader is not compatible with export.`

**解決策**:
```js
// next.config.js
images: {
  unoptimized: true,
}
```

### フォームが動かない

**原因**: FormspreeのIDが間違っている

**解決策**:
- company-data.jsonのformspreeIdを確認
- Formspreeの管理画面でForm IDを再確認

### 日本語フォントが表示されない

**解決策**:
```tsx
// app/layout.tsx
import { Noto_Sans_JP } from 'next/font/google'

const notoSansJP = Noto_Sans_JP({
  subsets: ['latin'],
  weight: ['400', '700']
})

export default function RootLayout({ children }) {
  return (
    <html lang="ja" className={notoSansJP.className}>
      <body>{children}</body>
    </html>
  )
}
```

---

**次のステップ**: [納品フロー](delivery-flow.md)を確認
