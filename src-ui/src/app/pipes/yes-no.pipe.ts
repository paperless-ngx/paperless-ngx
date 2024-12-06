import { Pipe, PipeTransform } from '@angular/core'

@Pipe({
  name: 'yesno',
  standalone: false,
})
export class YesNoPipe implements PipeTransform {
  transform(value: boolean): unknown {
    return value ? $localize`Yes` : $localize`No`
  }
}
