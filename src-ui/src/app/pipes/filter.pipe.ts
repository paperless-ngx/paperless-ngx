import { Pipe, PipeTransform } from '@angular/core'
import { MatchingModel } from '../data/matching-model'
import { textMatchesTokens } from '../utils/text-match'

@Pipe({
  name: 'filter',
})
export class FilterPipe implements PipeTransform {
  transform(
    items: MatchingModel[],
    searchText: string,
    key?: string
  ): MatchingModel[] {
    if (!items) return []
    if (!searchText) return items

    return items.filter((item) => {
      const keys = key
        ? [key]
        : Object.keys(item).filter(
            (key) =>
              typeof item[key] === 'string' || typeof item[key] === 'number'
          )
      return keys.some((key) => {
        return textMatchesTokens(String(item[key]), searchText)
      })
    })
  }
}
