import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { StoragePath } from 'src/app/data/storage-path'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class StoragePathService extends AbstractNameFilterService<StoragePath> {
  constructor() {
    super()
    this.resourceName = 'storage_paths'
  }

  public testPath(path: string, documentID: number): Observable<any> {
    return this.http.post<string>(`${this.getResourceUrl()}test/`, {
      path,
      document: documentID,
    })
  }
}
