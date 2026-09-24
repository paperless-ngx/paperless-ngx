import { environment } from 'src/environments/environment'

/**
 * Build the public URL for a share link (or bundle) slug. If a base URL is
 * configured (PAPERLESS_SHARE_LINK_BASE_URL) it is used, otherwise the URL is
 * derived from the API base URL so subpath installs work.
 */
export function getShareUrl(slug: string, baseUrl?: string): string {
  if (baseUrl) {
    return `${baseUrl.replace(/\/+$/, '')}/share/${slug}`
  }
  const apiURL = new URL(environment.apiBaseUrl)
  return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${slug}`
}
