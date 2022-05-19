import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class StoragePathService extends AbstractNameFilterService<PaperlessStoragePath> {
  constructor(http: HttpClient) {
    super(http, 'storage_paths')
  }
}
