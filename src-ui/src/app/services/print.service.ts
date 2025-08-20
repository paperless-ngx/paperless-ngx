import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { DeviceDetectorService } from 'ngx-device-detector'
import { ToastService } from './toast.service'

@Injectable({
  providedIn: 'root',
})
export class PrintService {
  protected http = inject(HttpClient)
  private toastService = inject(ToastService)
  private deviceDetectorService = inject(DeviceDetectorService)

  printDocument(printUrl: string): void {
    this.http.get(printUrl, { responseType: 'blob' }).subscribe({
      next: (blob) => {
        if (this.deviceDetectorService.isMobile()) {
          const blobUrl = URL.createObjectURL(blob)
          window.open(blobUrl, '_blank')
          setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
          return
        }

        const blobUrl = URL.createObjectURL(blob)
        const iframe = document.createElement('iframe')
        iframe.style.display = 'none'
        iframe.src = blobUrl
        document.body.appendChild(iframe)

        iframe.onload = () => {
          try {
            iframe.contentWindow.focus()
            iframe.contentWindow.print()
            iframe.contentWindow.onafterprint = () => {
              document.body.removeChild(iframe)
              URL.revokeObjectURL(blobUrl)
            }
          } catch (err) {
            this.toastService.showError($localize`Print failed.`, err)
            document.body.removeChild(iframe)
            URL.revokeObjectURL(blobUrl)
          }
        }
      },
      error: () => {
        this.toastService.showError(
          $localize`Error loading document for printing.`
        )
      },
    })
  }
}
