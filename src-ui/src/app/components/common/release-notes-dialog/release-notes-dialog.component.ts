import { Component, inject, signal } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import {
  AppRelease,
  RemoteVersionService,
} from 'src/app/services/rest/remote-version.service'
import { SettingsService } from 'src/app/services/settings.service'

const RELEASES_URL = 'https://github.com/paperless-ngx/paperless-ngx/releases'

/**
 * Tweak GitHub release HTML: open links in a new tab, add no referrer etc,
 * drop inline svgs and GH `data-*` attributes. Angular sanitizes all of this anyway.
 */
export function prepareReleaseHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.querySelectorAll('svg').forEach((svg) => svg.remove())
  doc.body.querySelectorAll('*').forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      if (attr.name.startsWith('data-')) el.removeAttribute(attr.name)
    }
  })
  doc.querySelectorAll('a').forEach((a) => {
    a.setAttribute('target', '_blank')
    a.setAttribute('rel', 'noopener noreferrer nofollow')
  })
  return doc.body.innerHTML
}

@Component({
  selector: 'pngx-release-notes-dialog',
  templateUrl: './release-notes-dialog.component.html',
  styleUrls: ['./release-notes-dialog.component.scss'],
  imports: [BootstrapIconComponent, CustomDatePipe],
})
export class ReleaseNotesDialogComponent {
  readonly activeModal = inject(NgbActiveModal)
  private readonly remoteVersionService = inject(RemoteVersionService)
  private readonly settingsService = inject(SettingsService)

  readonly since = signal<string | null>(null)
  readonly releases = signal<AppRelease[] | null>(null)
  readonly loading = signal(false)

  readonly version: string = this.settingsService.get(SETTINGS_KEYS.VERSION)
  readonly updateCheckingEnabled: boolean = this.settingsService.get(
    SETTINGS_KEYS.UPDATE_CHECKING_ENABLED
  )

  get releaseUrl(): string {
    return this.version ? `${RELEASES_URL}/tag/v${this.version}` : RELEASES_URL
  }

  /**
   * Load notes for releases after `since`, or the running version's
   * notes if `since` is null.
   */
  load(since: string | null): void {
    this.since.set(since)
    if (!this.updateCheckingEnabled) return
    this.loading.set(true)
    this.remoteVersionService
      .getReleaseNotes(since ?? undefined)
      .pipe(first())
      .subscribe({
        next: (notes) => {
          this.releases.set(
            notes.releases.map((release) => ({
              ...release,
              body_html: prepareReleaseHtml(release.body_html),
            }))
          )
          this.loading.set(false)
        },
        error: () => {
          this.releases.set([])
          this.loading.set(false)
        },
      })
  }

  close(): void {
    this.activeModal.close()
  }
}
