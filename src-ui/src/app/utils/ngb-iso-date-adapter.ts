import { Injectable } from '@angular/core'
import { NgbDateAdapter, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap'

@Injectable()
export class ISODateAdapter extends NgbDateAdapter<string> {
  fromModel(value: string | null): NgbDateStruct | null {
    if (value) {
      if (value.match(/\d\d\d\d\-\d\d\-\d\d/g)) {
        const segs = value.split('-')
        return {
          year: parseInt(segs[0]),
          month: parseInt(segs[1]),
          day: parseInt(segs[2]),
        }
      } else {
        let date = new Date(value)
        return {
          day: date.getDate(),
          month: date.getMonth() + 1,
          year: date.getFullYear(),
        }
      }
    } else {
      return null
    }
  }

  toModel(date: NgbDateStruct | null): string | null {
    if (date) {
      return (
        date.year.toString().padStart(4, '0') +
        '-' +
        date.month.toString().padStart(2, '0') +
        '-' +
        date.day.toString().padStart(2, '0')
      )
    } else {
      return null
    }
  }
}
