export type Source = 'olx' | 'krisha' | 'kolesa'
export type Dataset = 'real' | 'fixture'
export type RiskLevel = 'unknown' | 'low' | 'medium' | 'high'
export type CatalogView = 'all' | 'deals' | 'risk'

export interface Listing {
  id: string
  externalId: string
  source: Source
  dataset: Dataset
  url: string
  title: string
  description: string | null
  category: string
  subcategory: string | null
  price: number | null
  currency: string | null
  city: string | null
  images: string[]
  attributes: Record<string, unknown>
  condition: string | null
  publishedAt: string | null
  scrapedAt: string
  sellerId: string | null
}

export interface AnalysisResult {
  listingId: string
  listingScrapedAt: string
  computedAt: string
  algorithmVersion: string
  comparableGroup: string | null
  marketPrice: number | null
  priceDeviationPercent: number | null
  savingsAmount: number | null
  dealScore: number | null
  riskScore: number | null
  riskLevel: RiskLevel
  riskReasons: { code: string; description: string }[]
  confidence: number | null
  sampleSize: number
  isDeal: boolean
}

export interface ListingItem {
  listing: Listing
  analysis: AnalysisResult | null
}

export interface ListingPage {
  items: ListingItem[]
  nextOffset: number | null
  scannedCount: number
  scanLimited: boolean
  total?: number
  subcategoryCounts?: Record<string, number>
  subcategoryCovers?: Record<string, string>
  latestScrapedAt?: string | null
}

export interface MarketStats {
  dataset: Dataset
  computedAt: string
  comparableGroup: string
  category: string
  currency: string
  sampleSize: number
  meanPrice: number | null
  medianPrice: number | null
  minPrice: number | null
  maxPrice: number | null
  histogram: { min: number; max: number; count: number }[]
}

export interface StatsPage {
  items: MarketStats[]
  truncated: boolean
}

export interface Explanation {
  provider: 'local' | 'gemini' | 'openai'
  summary: string
  insights: string[]
  recommendations: string[]
  limitations: string[]
}

export interface PriceHistory {
  items: { scrapedAt: string; price: number | null; currency: string | null }[]
  truncated: boolean
}
