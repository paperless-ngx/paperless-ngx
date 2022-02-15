import { Injectable } from "@angular/core"
import { NgbDateParserFormatter, NgbDateStruct } from "@ng-bootstrap/ng-bootstrap"
import { SettingsService } from "../services/settings.service"

@Injectable()
export class LocalizedDateParserFormatter extends NgbDateParserFormatter {

  constructor(private settings: SettingsService) {
    super()
  }

  private getDateInputFormat() {
    return this.settings.getLocalizedDateInputFormat()
  }

  /**
   * This constructs a regular expression from a date input format which is then
   * used to parse dates.
   */
  private getDateParseRegex() {
    return new RegExp(
      "^" + this.getDateInputFormat()
      .replace('dd', '(?<day>[0-9]+)')
      .replace('mm', '(?<month>[0-9]+)')
      .replace('yyyy', '(?<year>[0-9]+)')
      .split('.').join('\\.\\s*') + "$" // allow whitespace(s) after dot (specific for German)
      )
  }

  parse(value: string): NgbDateStruct | null {
    let match = this.getDateParseRegex().exec(value)
    if (match) {
      let dateStruct = {
        day: +match.groups.day,
        month: +match.groups.month,
        year: +match.groups.year
      }
      if (dateStruct.year <= (new Date().getFullYear() - 2000)) {
        dateStruct.year += 2000
      } else if (dateStruct.year < 100) {
        dateStruct.year += 1900
      }
      return dateStruct
    } else {
      return null
    }
  }

  format(date: NgbDateStruct | null): string {
    if (date) {
      return this.getDateInputFormat()
      .replace('dd', date.day.toString().padStart(2, '0'))
      .replace('mm', date.month.toString().padStart(2, '0'))
      .replace('yyyy', date.year.toString().padStart(4, '0'))
    } else {
      return null
    }
  }
}
