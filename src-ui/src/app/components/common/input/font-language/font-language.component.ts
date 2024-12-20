import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { first } from 'rxjs/operators'
import { FontLanguage } from 'src/app/data/font-language'
import { FontLanguageService } from 'src/app/services/rest/font-language.service'
import { SettingsService } from 'src/app/services/settings.service'
import { AbstractInputComponent } from '../abstract-input'


@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => FontLanguageComponentInput),
      multi: true,
    },
  ],
  selector: 'pngx-font-language-input',
  templateUrl: './font-language.component.html',
  styleUrls: ['./font-language.component.scss'],
})
export class FontLanguageComponentInput extends AbstractInputComponent<FontLanguage[]> {
  fontLanguages: FontLanguage[]

  constructor(fontLanguageService: FontLanguageService, settings: SettingsService) {
    super()
    fontLanguageService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.fontLanguages = result.results))
  }
}
