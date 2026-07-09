import { Clipboard } from '@angular/cdk/clipboard'
import { Component, OnInit, effect, inject, input, signal } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { first } from 'rxjs'
import {
  FileVersion,
  SHARE_LINK_EXPIRATION_OPTIONS,
  ShareLink,
} from 'src/app/data/share-link'
import { ShareLinkService } from 'src/app/services/rest/share-link.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-share-links-dialog',
  templateUrl: './share-links-dialog.component.html',
  styleUrls: ['./share-links-dialog.component.scss'],
  imports: [FormsModule, ReactiveFormsModule, NgxBootstrapIconsModule],
})
export class ShareLinksDialogComponent implements OnInit {
  private activeModal = inject(NgbActiveModal)
  private shareLinkService = inject(ShareLinkService)
  private toastService = inject(ToastService)
  private clipboard = inject(Clipboard)

  readonly expirationOptions = SHARE_LINK_EXPIRATION_OPTIONS

  readonly title = input($localize`Share Links`)
  readonly documentId = signal<number>(undefined)
  readonly hasArchiveVersion = signal(true)
  readonly shareLinks = signal<ShareLink[]>(undefined)
  readonly loading = signal(false)
  readonly copied = signal<number>(undefined)

  expirationDays: number = 7
  useArchiveVersion: boolean = true

  constructor() {
    effect(() => {
      const id = this.documentId()
      if (id !== undefined) this.refresh()
    })
    effect(() => {
      this.useArchiveVersion = this.hasArchiveVersion()
    })
  }

  ngOnInit(): void {
    if (this.documentId() !== undefined) this.refresh()
  }

  refresh() {
    if (this.documentId() === undefined) return
    this.loading.set(true)
    this.shareLinkService
      .getLinksForDocument(this.documentId())
      .pipe(first())
      .subscribe({
        next: (results) => {
          this.loading.set(false)
          this.shareLinks.set(results)
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error retrieving links`,
            10000,
            e
          )
        },
      })
  }

  getShareUrl(link: ShareLink): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      link.slug
    }`
  }

  getDaysRemaining(link: ShareLink): string {
    const days: number = Math.round(
      (Date.parse(link.expiration) - Date.now()) / (1000 * 60 * 60 * 24)
    )
    return days === 1 ? $localize`1 day` : $localize`${days} days`
  }

  copy(link: ShareLink) {
    const success = this.clipboard.copy(this.getShareUrl(link))
    if (success) {
      this.copied.set(link.id)
      setTimeout(() => {
        this.copied.set(null)
      }, 3000)
    }
  }

  canShare(link: ShareLink): boolean {
    return (
      navigator?.canShare && navigator.canShare({ url: this.getShareUrl(link) })
    )
  }

  share(link: ShareLink) {
    navigator.share({ url: this.getShareUrl(link) })
  }

  delete(link: ShareLink) {
    this.shareLinkService.delete(link).subscribe({
      next: () => {
        this.refresh()
      },
      error: (e) => {
        this.toastService.showError($localize`Error deleting link`, 10000, e)
      },
    })
  }

  createLink() {
    let expiration
    if (this.expirationDays) {
      expiration = new Date()
      expiration.setDate(expiration.getDate() + this.expirationDays)
    }
    this.loading.set(true)
    this.shareLinkService
      .createLinkForDocument(
        this.documentId(),
        this.useArchiveVersion ? FileVersion.Archive : FileVersion.Original,
        expiration
      )
      .subscribe({
        next: (result) => {
          this.loading.set(false)
          setTimeout(() => {
            this.copy(result)
          }, 10)
          this.refresh()
        },
        error: (e) => {
          this.loading.set(false)
          this.toastService.showError($localize`Error creating link`, 10000, e)
        },
      })
  }

  close() {
    this.activeModal.close()
  }
}
