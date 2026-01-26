import { Component, HostListener, inject } from '@angular/core'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'

@Component({
  selector: 'pngx-file-drop',
  templateUrl: './file-drop.component.html',
  styleUrls: ['./file-drop.component.scss'],
  imports: [],
})
export class FileDropComponent {
  private settings = inject(SettingsService)
  private toastService = inject(ToastService)
  private uploadDocumentsService = inject(UploadDocumentsService)
  private permissionsService = inject(PermissionsService)

  private fileLeaveTimeoutID: any
  fileIsOver: boolean = false
  hidden: boolean = true

  public get dragDropEnabled(): boolean {
    return (
      this.settings.globalDropzoneEnabled &&
      this.permissionsService.currentUserCan(
        PermissionAction.Add,
        PermissionType.Document
      )
    )
  }

  @HostListener('document:dragover', ['$event']) onDragOver(event: DragEvent) {
    if (!this.dragDropEnabled || !event.dataTransfer?.types?.includes('Files'))
      return
    event.preventDefault()
    event.stopImmediatePropagation()
    this.settings.globalDropzoneActive = true
    // allows transition
    setTimeout(() => {
      this.fileIsOver = true
    }, 1)
    this.hidden = false
    // stop fileLeave timeout
    clearTimeout(this.fileLeaveTimeoutID)
  }

  @HostListener('document:dragleave', ['$event']) public onDragLeave(
    event: DragEvent,
    immediate: boolean = false
  ) {
    if (!this.dragDropEnabled) return
    event?.preventDefault()
    event?.stopImmediatePropagation()
    this.settings.globalDropzoneActive = false

    const ms = immediate ? 0 : 500

    this.fileLeaveTimeoutID = setTimeout(() => {
      this.fileIsOver = false
      // await transition completed
      setTimeout(() => {
        this.hidden = true
      }, 150)
    }, ms)
  }

  private traverseFileTree(entry: FileSystemEntry): Promise<File[]> {
    if (entry.isFile) {
      return new Promise((resolve, reject) => {
        ;(entry as FileSystemFileEntry).file(resolve, reject)
      }).then((file: File) => [file])
    }

    if (entry.isDirectory) {
      return new Promise<File[]>((resolve, reject) => {
        const dirReader = (entry as FileSystemDirectoryEntry).createReader()
        const allEntries: FileSystemEntry[] = []

        const readEntries = () => {
          dirReader.readEntries((batch) => {
            if (batch.length === 0) {
              const promises = allEntries.map((child) =>
                this.traverseFileTree(child)
              )
              Promise.all(promises)
                .then((results) => resolve([].concat(...results)))
                .catch(reject)
            } else {
              allEntries.push(...batch)
              readEntries() // keep reading
            }
          }, reject)
        }

        readEntries()
      })
    }

    return Promise.resolve([])
  }

  @HostListener('document:drop', ['$event']) public onDrop(event: DragEvent) {
    if (!this.dragDropEnabled) return
    event.preventDefault()
    event.stopImmediatePropagation()

    const files: File[] = []
    const entries: FileSystemEntry[] = []
    if (event.dataTransfer?.items && event.dataTransfer.items.length) {
      for (const item of Array.from(event.dataTransfer.items)) {
        if (item.webkitGetAsEntry) {
          // webkitGetAsEntry not standard, but is widely supported
          const entry = item.webkitGetAsEntry()
          if (entry) entries.push(entry)
        } else if (item.kind === 'file') {
          const file = item.getAsFile()
          if (file) files.push(file)
        }
      }
    } else if (event.dataTransfer?.files) {
      // Fallback for browsers without DataTransferItem API
      for (const file of Array.from(event.dataTransfer.files)) {
        files.push(file)
      }
    }

    if (entries.length) {
      const promises = entries.map((entry) => this.traverseFileTree(entry))
      Promise.all(promises)
        .then((results) => {
          files.push(...[].concat(...results))
          this.toastService.showInfo($localize`Initiating upload...`, 3000)
          files.forEach((file) => this.uploadDocumentsService.uploadFile(file))
        })
        .catch((e) => {
          this.toastService.showError(
            $localize`Failed to read dropped items: ${e.message}`
          )
        })
    } else if (files.length) {
      this.toastService.showInfo($localize`Initiating upload...`, 3000)
      files.forEach((file) => this.uploadDocumentsService.uploadFile(file))
    }

    this.onDragLeave(event, true)
  }

  @HostListener('window:blur') public onWindowBlur() {
    if (this.fileIsOver) this.onDragLeave(null)
  }

  @HostListener('document:visibilitychange') public onVisibilityChange() {
    if (document.hidden && this.fileIsOver) this.onDragLeave(null)
  }
}
