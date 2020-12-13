import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'documentTitle'
})
export class DocumentTitlePipe implements PipeTransform {

  transform(value: string): unknown {
    if (value) {
      return value
    } else {
      return "(no title)"
    }
  }

}
