import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { CsrfService } from './csrf.service'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  constructor(private csrfService: CsrfService) {}

  streamChat(documentId: number, prompt: string): Observable<string> {
    return new Observable<string>((observer) => {
      const url = `${environment.apiBaseUrl}documents/chat/`
      const xhr = new XMLHttpRequest()
      let lastLength = 0

      xhr.open('POST', url)
      xhr.setRequestHeader('Content-Type', 'application/json')

      xhr.withCredentials = true
      let csrfToken = this.csrfService.getToken()
      if (csrfToken) {
        xhr.setRequestHeader('X-CSRFToken', csrfToken)
      }

      xhr.onreadystatechange = () => {
        if (xhr.readyState === 3 || xhr.readyState === 4) {
          const partial = xhr.responseText.slice(lastLength)
          lastLength = xhr.responseText.length

          if (partial) {
            observer.next(partial)
          }
        }

        if (xhr.readyState === 4) {
          observer.complete()
        }
      }

      xhr.onerror = () => {
        observer.error(new Error('Streaming request failed.'))
      }

      const body = JSON.stringify({
        document_id: documentId,
        q: prompt,
      })

      xhr.send(body)
    })
  }
}
