import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'
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
