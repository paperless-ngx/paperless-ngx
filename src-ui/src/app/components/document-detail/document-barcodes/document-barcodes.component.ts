import { Clipboard } from '@angular/cdk/clipboard'
import { Component, inject, input, OnDestroy, signal } from '@angular/core'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { DocumentBarcode } from 'src/app/data/document-barcode'

@Component({
  selector: 'pngx-document-barcodes',
  templateUrl: './document-barcodes.component.html',
  imports: [BootstrapIconComponent],
})
export class DocumentBarcodesComponent implements OnDestroy {
  private readonly clipboard = inject(Clipboard)

  readonly barcodes = input<DocumentBarcode[]>([])

  readonly copiedIndex = signal<number>(null)
  private copyTimeout: ReturnType<typeof setTimeout>

  public isLink(value: string): boolean {
    try {
      const url = new URL(value.trim())
      return ['http:', 'https:'].includes(url.protocol) && !!url.host
    } catch {
      return false
    }
  }

  public copy(index: number) {
    if (!this.clipboard.copy(this.barcodes()[index].value)) return
    this.copiedIndex.set(index)
    clearTimeout(this.copyTimeout)
    this.copyTimeout = setTimeout(() => this.copiedIndex.set(null), 3000)
  }

  ngOnDestroy(): void {
    clearTimeout(this.copyTimeout)
  }
}
