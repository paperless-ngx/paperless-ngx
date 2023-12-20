import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { StoragePath } from 'src/app/data/storage-path'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class StoragePathService extends AbstractNameFilterService<StoragePath> {
  constructor(http: HttpClient) {
    super(http, 'storage_paths')
  }
}
