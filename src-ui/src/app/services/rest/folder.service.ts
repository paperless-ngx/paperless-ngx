import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { Folder } from 'src/app/data/folder'
import { Results } from 'src/app/data/results'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class FolderService extends AbstractNameFilterService<Folder> {
  constructor() {
    super()
    this.resourceName = 'folders'
  }

  /**
   * Returns the folder tree starting from the root folders, with children
   * nested by the backend.
   */
  getTree(): Observable<Results<Folder>> {
    return this.list(1, 100000, 'name', false, { is_root: true })
  }
}
