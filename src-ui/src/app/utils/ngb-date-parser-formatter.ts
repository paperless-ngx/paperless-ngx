import { Injectable } from '@angular/core'
import {
  NgbDateParserFormatter,
  NgbDateStruct,
} from '@ng-bootstrap/ng-bootstrap'
import { SettingsService } from '../services/settings.service'

@Injectable()
export class LocalizedDateParserFormatter extends NgbDateParserFormatter {
  private separatorRegExp: RegExp = /[\.,\/-]+/

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
      '^' +
        this.getDateInputFormat()
          .replace('dd', '(?<day>[0-9]+)')
          .replace('mm', '(?<month>[0-9]+)')
          .replace('yyyy', '(?<year>[0-9]+)')
          .split('.')
          .join('\\.\\s*') +
        '$' // allow whitespace(s) after dot (specific for German)
    )
  }

  /**
   * This adds date separators if none are entered.
   * It also adds the current year if it wasn't entered.
   *
   * This allows users to just enter 1003, 100322, 10032022 and
   * have it expanded to 10.03.2022, in the case of the German format.
   * (All other formats are also supported)
   *
   * It also strips any separators before running formatting and pads
   * any parts of the string, e.g. allowing for 1/2/22,
   * which allows quick entry of the date on the numpad.
   */
  private preformatDateInput(value: string): string {
    const inputFormat = this.getDateInputFormat()
    const dateSeparator = inputFormat.replace(/[dmy]/gi, '').charAt(0)

    if (this.separatorRegExp.test(value)) {
      let segments = value.split(this.separatorRegExp)

      // always accept strict yyyy*mm*dd format even if that's not the input format since we can be certain its not yyyy*dd*mm
      if (
        value.length == 10 &&
        segments.length == 3 &&
        segments[0].length == 4
      ) {
        return inputFormat
          .replace('yyyy', segments[0])
          .replace('mm', segments[1])
          .replace('dd', segments[2])
      } else {
        // otherwise pad & re-join without separator
        value = segments.map((segment) => segment.padStart(2, '0')).join('')
      }
    }

    if (value.length == 4 && inputFormat.substring(0, 4) != 'yyyy') {
      return [
        value.substring(0, 2),
        value.substring(2, 4),
        new Date().getFullYear(),
      ].join(dateSeparator)
    } else if (value.length == 4 && inputFormat.substring(0, 4) == 'yyyy') {
      return [
        new Date().getFullYear(),
        value.substring(0, 2),
        value.substring(2, 4),
      ].join(dateSeparator)
    } else if (value.length == 6) {
      return [
        value.substring(0, 2),
        value.substring(2, 4),
        value.substring(4, 6),
      ].join(dateSeparator)
    } else if (value.length == 8 && inputFormat.substring(0, 4) != 'yyyy') {
      return [
        value.substring(0, 2),
        value.substring(2, 4),
        value.substring(4, 8),
      ].join(dateSeparator)
    } else if (value.length == 8 && inputFormat.substring(0, 4) == 'yyyy') {
      return [
        value.substring(0, 4),
        value.substring(4, 6),
        value.substring(6, 8),
      ].join(dateSeparator)
    } else {
      return value
    }
  }

  parse(value: string): NgbDateStruct | null {
    value = this.preformatDateInput(value)
    let match = this.getDateParseRegex().exec(value)
    if (match) {
      let dateStruct = {
        day: +match.groups.day,
        month: +match.groups.month,
        year: +match.groups.year,
      }
      if (dateStruct.year <= new Date().getFullYear() - 2000) {
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
