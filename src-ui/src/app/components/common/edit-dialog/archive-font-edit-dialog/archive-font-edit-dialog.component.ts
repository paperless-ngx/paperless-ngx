import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { ArchiveFont } from 'src/app/data/archive-font'
import { TagService } from 'src/app/services/rest/tag.service'
import { randomColor } from 'src/app/utils/color'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { FontLanguage } from 'src/app/data/font-language'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ArchiveFontService } from 'src/app/services/rest/archive-font.service'
import { FontLanguageService } from 'src/app/services/rest/font-language.service'
import { first } from 'rxjs'

@Component({
  selector: 'pngx-archive-font-edit-dialog',
  templateUrl: './archive-font-edit-dialog.component.html',
  styleUrls: ['./archive-font-edit-dialog.component.scss'],
})
export class ArchiveFontEditDialogComponent extends EditDialogComponent<ArchiveFont> {
  fontLanguages: FontLanguage[]
  constructor(
    service: ArchiveFontService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    fontLanguageService: FontLanguageService
  ) {
    super(service, activeModal, userService, settingsService)
    fontLanguageService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.fontLanguages = result.results))
  }

  getCreateTitle() {
    return $localize`Create new font language`
  }

  getEditTitle() {
    return $localize`Edit font language`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      // color: new FormControl(randomColor()),
      // is_inbox_tag: new FormControl(false),
      languages: new FormControl(),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
