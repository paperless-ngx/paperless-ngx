import { Component, inject, signal } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { MarkdownPipe } from 'src/app/pipes/markdown.pipe'
import {
  AppRelease,
  RemoteVersionService,
} from 'src/app/services/rest/remote-version.service'
import { SettingsService } from 'src/app/services/settings.service'

const RELEASES_URL = 'https://github.com/paperless-ngx/paperless-ngx/releases'

const RELEASE_TITLE = /^\s*##\s+paperless-ngx[^\n]*\n+/i
const ALL_CHANGES_SECTION = /^###\s+All App Changes\s*$[\s\S]*/im
const DETAILS_MARKUP = /^\s*(<\/?details>|<summary>.*<\/summary>)\s*$/gim

/**
 * Drops the "## paperless-ngx x.y.z" title, the "All App Changes"
 * section and `<details>` / `<summary>` wrappers.
 */
export function cleanReleaseBody(body: string): string {
  body = body.replace(RELEASE_TITLE, '')
  body = body.replace(ALL_CHANGES_SECTION, '')
  return body.replace(DETAILS_MARKUP, '').trim()
}

@Component({
  selector: 'pngx-release-notes-dialog',
  templateUrl: './release-notes-dialog.component.html',
  styleUrls: ['./release-notes-dialog.component.scss'],
  imports: [BootstrapIconComponent, MarkdownPipe],
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
              body: cleanReleaseBody(release.body),
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
