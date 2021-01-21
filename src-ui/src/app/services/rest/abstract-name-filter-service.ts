import { ObjectWithId } from 'src/app/data/object-with-id'
import { AbstractPaperlessService } from './abstract-paperless-service'

export abstract class AbstractNameFilterService<T extends ObjectWithId> extends AbstractPaperlessService<T> {

  listFiltered(page?: number, pageSize?: number, sortField?: string, sortReverse?: boolean, nameFilter?: string) {
    let params = {}
    if (nameFilter) {
      params = {'name__icontains': nameFilter}
    }
    return this.list(page, pageSize, sortField, sortReverse, params)
  }

}
