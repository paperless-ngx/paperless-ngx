import { HttpEvent, HttpEventType } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop'
import { Subscription } from 'rxjs'
import {
  ConsumerStatusService,
  FileStatus,
  FileStatusPhase,
} from './consumer-status.service'
import { DocumentService } from './rest/document.service'
import { SettingsService } from './settings.service'

interface UploadFilesCustomOptions {
  storagePathId?: number;
  isUploadWithFolders?: boolean;
  isLargeFile?: boolean;
  ocrSpecificPages?: string;
}

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private uploadSubscriptions: Array<Subscription> = []

  constructor(
    private documentService: DocumentService,
    private consumerStatusService: ConsumerStatusService,
    private settings: SettingsService
  ) { }

  uploadFiles(files: NgxFileDropEntry[], options: UploadFilesCustomOptions) {
    for (const droppedFile of files) {
      if (!droppedFile.fileEntry.isFile) continue;
      const fileEntry = droppedFile.fileEntry as FileSystemFileEntry
      fileEntry.file((file: File) => {
        let formData = new FormData()
        formData.append('document', file, file.name)
        this.appendExtraOptions(fileEntry, formData, options);

        let status = this.consumerStatusService.newFileUpload(file.name)
        status.message = $localize`Connecting...`

        this.uploadSubscriptions[file.name] = this.documentService
          .uploadDocument(formData)
          .subscribe({
            next: (event) => this.updateProgress(status, event, file),
            error: (error) => this.handleError(status, error, file),
          })
      })
    }
  }

  private appendExtraOptions(fileEntry: FileSystemFileEntry, formData: FormData, options: UploadFilesCustomOptions) {
    // Upload folders & files following the original folder structure feature
    if (options.isUploadWithFolders && 'fullPath' in fileEntry) {
      // I don't remember why but this just works.
      formData.append('full_path', (fileEntry as any).fullPath)
    }

    // Upload file to specific folder feature
    if (options.storagePathId) {
      formData.append('storage_path_id', options.storagePathId.toString())
    }

    // Large file upload with OCR pages feature
    if (options.isLargeFile) formData.append('is_large_file', 'true');
    if (options.ocrSpecificPages) formData.append('ocr_specific_pages', options.ocrSpecificPages);
  }

  private updateProgress(status: FileStatus, event: HttpEvent<Object>, file: File) {
    if (event.type == HttpEventType.UploadProgress) {
      status.updateProgress(
        FileStatusPhase.UPLOADING,
        event.loaded,
        event.total
      )
      status.message = $localize`Uploading...`
    } else if (event.type == HttpEventType.Response) {
      status.taskId = event.body['task_id']
      status.message = $localize`Upload complete, waiting...`
      this.uploadSubscriptions[file.name]?.complete()
    }
  }

  private handleError(status: FileStatus, error: any, file: File) {
    switch (error.status) {
      case 400: {
        this.consumerStatusService.fail(
          status,
          error.error.document
        )
        break
      }
      default: {
        this.consumerStatusService.fail(
          status,
          $localize`HTTP error: ${error.status} ${error.statusText}`
        )
        break
      }
    }
    this.uploadSubscriptions[file.name]?.complete()
  }
}
