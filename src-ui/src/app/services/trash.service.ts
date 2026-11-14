import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'
import { Results } from '../data/results'
import { DocumentListViewService } from './document-list-view.service'
import { TaskNotificationService } from './task-notification.service'
import { Toast, ToastLevel, ToastService } from './toast.service'

@Injectable({
  providedIn: 'root',
})
export class TrashService {
  private http = inject(HttpClient)
  private toastService = inject(ToastService)
  private documentListViewService = inject(DocumentListViewService)
  private taskNotifications = inject(TaskNotificationService)

  public trackMovedToTrash(
    taskId: string,
    count: number,
    documents?: number[]
  ) {
    this.taskNotifications.showQueued(
      taskId,
      count > 1
        ? $localize`Bulk move to trash queued.`
        : $localize`Move to trash queued.`,
      this.movedToTrashToast(
        $localize`Moved ${count} document(s) to the trash`,
        documents
      )
    )
  }

  public getTrash(page: number = 1): Observable<Results<Document>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Document>>(`${environment.apiBaseUrl}trash/`, {
      params: httpParams,
    })
  }

  public emptyTrash(documents?: number[]): Observable<any> {
    const data = {
      action: 'empty',
    }
    if (documents?.length) {
      data['documents'] = documents
    }
    return this.http.post(`${environment.apiBaseUrl}trash/`, data)
  }

  public restoreDocuments(documents: number[]): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}trash/`, {
      action: 'restore',
      documents,
    })
  }

  /**
   * Shows a toast with an Undo action when possible
   */
  public notifyMovedToTrash(content: string, documents?: number[]) {
    this.toastService.show(this.movedToTrashToast(content, documents))
  }

  private movedToTrashToast(content: string, documents?: number[]): Toast {
    const canUndo = documents?.length > 0
    return {
      content,
      delay: 10000,
      level: ToastLevel.Success,
      ...(canUndo
        ? {
            actionName: $localize`Undo`,
            action: () => this.undoMoveToTrash(documents),
          }
        : {}),
    }
  }

  private undoMoveToTrash(documents: number[]) {
    this.restoreDocuments(documents).subscribe({
      next: () => {
        this.toastService.show({
          content: $localize`Document(s) restored`,
          delay: 5000,
          level: ToastLevel.Success,
        })
        this.documentListViewService.reload()
      },
      error: (e) => {
        this.toastService.showError($localize`Error restoring document(s)`, e)
      },
    })
  }
}
