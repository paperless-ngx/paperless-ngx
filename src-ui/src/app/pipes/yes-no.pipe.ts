import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'yesno'
})
export class YesNoPipe implements PipeTransform {

  transform(value: boolean): unknown {
    return value ? "Yes" : "No"
  }

}
