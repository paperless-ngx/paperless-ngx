import { Injectable } from "@angular/core";
import { NgbDateAdapter, NgbDateStruct } from "@ng-bootstrap/ng-bootstrap";

@Injectable()
export class ISODateTimeAdapter extends NgbDateAdapter<string> {

  fromModel(value: string | null): NgbDateStruct | null {
    if (value) {
      let date = new Date(value)
      return {
        day : date.getDate(),
        month : date.getMonth() + 1,
        year : date.getFullYear()
      }
    } else {
      return null
    }
  }

  toModel(date: NgbDateStruct | null): string | null {
    return date ? new Date(date.year, date.month - 1, date.day).toISOString() : null
  }
}
