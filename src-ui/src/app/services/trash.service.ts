import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'
import { PaperlessTaskStatus } from '../data/paperless-task'
import { Results } from '../data/results'
import { DocumentListViewService } from './document-list-view.service'
import { ToastLevel, ToastService } from './toast.service'

@Injectable({
  providedIn: 'root',
})
export class TrashService {
  private http = inject(HttpClient)
  private toastService = inject(ToastService)
  private documentListViewService = inject(DocumentListViewService)
  private pendingMoves = new Map<
    string,
    { count: number; documents?: number[] }
  >()
  private completedMoves = new Map<string, PaperlessTaskStatus>()

  public trackMovedToTrash(
    taskId: string,
    count: number,
    documents?: number[]
  ) {
    const status = this.completedMoves.get(taskId)
    if (status !== undefined) {
      this.completedMoves.delete(taskId)
      if (status === PaperlessTaskStatus.Success) {
        this.notifyMovedToTrash(
          $localize`Moved ${count} document(s) to the trash`,
          documents
        )
      }
    } else {
      this.pendingMoves.set(taskId, { count, documents })
    }
  }

  public handleDeleteTaskStatus(taskId: string, status: PaperlessTaskStatus) {
    const move = this.pendingMoves.get(taskId)
    if (move) {
      this.pendingMoves.delete(taskId)
      if (status === PaperlessTaskStatus.Success) {
        this.notifyMovedToTrash(
          $localize`Moved ${move.count} document(s) to the trash`,
          move.documents
        )
      }
    } else {
      // in case the task finishes fast
      this.completedMoves.set(taskId, status)
      if (this.completedMoves.size > 100) {
        this.completedMoves.delete(this.completedMoves.keys().next().value)
      }
    }
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
    const canUndo = documents?.length > 0
    this.toastService.show({
      content,
      delay: 10000,
      level: ToastLevel.Success,
      actionName: canUndo ? $localize`Undo` : undefined,
      action: canUndo ? () => this.undoMoveToTrash(documents) : undefined,
    })
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
