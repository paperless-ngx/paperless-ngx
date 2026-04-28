import {
  HttpClient,
  HttpDownloadProgressEvent,
  HttpEventType,
} from '@angular/common/http'
import { inject, Injectable } from '@angular/core'
import { filter, map, Observable } from 'rxjs'
import { environment } from 'src/environments/environment'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  references?: ChatReference[]
}

export interface ChatReference {
  id: number
  title: string
}

export interface ParsedChatResponse {
  content: string
  references?: ChatReference[]
}

export const CHAT_METADATA_DELIMITER = '\n\n__PAPERLESS_CHAT_METADATA__'

export function parseChatResponse(response: string): ParsedChatResponse {
  const delimiterIndex = response.indexOf(CHAT_METADATA_DELIMITER)

  if (delimiterIndex === -1) {
    return { content: response }
  }

  const metadataString = response.slice(
    delimiterIndex + CHAT_METADATA_DELIMITER.length
  )

  try {
    const metadata = JSON.parse(metadataString) as {
      references?: ChatReference[]
    }

    return {
      content: response.slice(0, delimiterIndex),
      references: metadata.references ?? [],
    }
  } catch {
    return {
      content: response.slice(0, delimiterIndex),
    }
  }
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private http: HttpClient = inject(HttpClient)

  streamChat(documentId: number, prompt: string): Observable<string> {
    return this.http
      .post(
        `${environment.apiBaseUrl}documents/chat/`,
        {
          document_id: documentId,
          q: prompt,
        },
        {
          observe: 'events',
          reportProgress: true,
          responseType: 'text',
          withCredentials: true,
        }
      )
      .pipe(
        map((event) => {
          if (event.type === HttpEventType.DownloadProgress) {
            return (event as HttpDownloadProgressEvent).partialText!
          }
        }),
        filter((chunk) => !!chunk)
      )
  }
}
