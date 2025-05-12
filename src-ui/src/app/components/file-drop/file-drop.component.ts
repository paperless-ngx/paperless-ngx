import { Component, HostListener } from '@angular/core'
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
  private fileLeaveTimeoutID: any
  fileIsOver: boolean = false
  hidden: boolean = true

  constructor(
    private settings: SettingsService,
    private toastService: ToastService,
    private uploadDocumentsService: UploadDocumentsService,
    private permissionsService: PermissionsService
  ) {}

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

  @HostListener('document:drop', ['$event']) public onDrop(event: DragEvent) {
    if (!this.dragDropEnabled) return
    event.preventDefault()
    event.stopImmediatePropagation()
    console.log('document:drop:', event)
    console.log('event.dataTransfer:', event.dataTransfer)
    console.log('event.dataTransfer.files:', event.dataTransfer?.files)

    const files = event.dataTransfer?.files
    if (files && files.length > 0) {
      this.uploadDocumentsService.uploadFiles(files)
      this.toastService.showInfo($localize`Initiating upload...`, 3000)
    }

    this.onDragLeave(event, true)
  }

  @HostListener('window:blur', ['$event']) public onWindowBlur() {
    if (this.fileIsOver) this.onDragLeave(null)
  }

  @HostListener('document:visibilitychange', ['$event'])
  public onVisibilityChange() {
    if (document.hidden && this.fileIsOver) this.onDragLeave(null)
  }
}
