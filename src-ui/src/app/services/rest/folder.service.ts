import { Injectable } from '@angular/core'
import { Folder } from 'src/app/data/folder'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class FolderService extends AbstractNameFilterService<Folder> {
  constructor() {
    super()
    this.resourceName = 'folders'
  }
}
