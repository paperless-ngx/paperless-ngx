import { Pipe, PipeTransform } from '@angular/core'

@Pipe({
  name: 'documentTitle',
})
export class DocumentTitlePipe implements PipeTransform {
  transform(value: string): string {
    if (value) {
      return value
    } else {
      return $localize`(no title)`
    }
  }
}
