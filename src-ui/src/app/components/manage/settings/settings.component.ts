import { Component, Inject, LOCALE_ID, OnInit, Renderer2  } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { LanguageOption, SettingsService, SETTINGS_KEYS } from 'src/app/services/settings.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss']
})
export class SettingsComponent implements OnInit {

  savedViewGroup = new FormGroup({})

  settingsForm = new FormGroup({
    'bulkEditConfirmationDialogs': new FormControl(this.settings.get(SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS)),
    'bulkEditApplyOnClose': new FormControl(this.settings.get(SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE)),
    'documentListItemPerPage': new FormControl(this.settings.get(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)),
    'darkModeUseSystem': new FormControl(this.settings.get(SETTINGS_KEYS.DARK_MODE_USE_SYSTEM)),
    'darkModeEnabled': new FormControl(this.settings.get(SETTINGS_KEYS.DARK_MODE_ENABLED)),
    'darkModeInvertThumbs': new FormControl(this.settings.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)),
    'useNativePdfViewer': new FormControl(this.settings.get(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER)),
    'savedViews': this.savedViewGroup,
    'displayLanguage': new FormControl(this.settings.getLanguage()),
    'dateLocale': new FormControl(this.settings.get(SETTINGS_KEYS.DATE_LOCALE)),
    'dateFormat': new FormControl(this.settings.get(SETTINGS_KEYS.DATE_FORMAT)),
    'notificationsConsumerNewDocument': new FormControl(this.settings.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT)),
    'notificationsConsumerSuccess': new FormControl(this.settings.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS)),
    'notificationsConsumerFailed': new FormControl(this.settings.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED)),
    'notificationsConsumerSuppressOnDashboard': new FormControl(this.settings.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD)),
  })

  savedViews: PaperlessSavedView[]

  get computedDateLocale(): string {
    return this.settingsForm.value.dateLocale || this.settingsForm.value.displayLanguage || this.currentLocale
  }

  constructor(
    public savedViewService: SavedViewService,
    private documentListViewService: DocumentListViewService,
    private toastService: ToastService,
    private settings: SettingsService,
    @Inject(LOCALE_ID) public currentLocale: string
  ) { }

  ngOnInit() {
    this.savedViewService.listAll().subscribe(r => {
      this.savedViews = r.results
      for (let view of this.savedViews) {
        this.savedViewGroup.addControl(view.id.toString(), new FormGroup({
          "id": new FormControl(view.id),
          "name": new FormControl(view.name),
          "show_on_dashboard": new FormControl(view.show_on_dashboard),
          "show_in_sidebar": new FormControl(view.show_in_sidebar)
        }))
      }
    })
  }

  deleteSavedView(savedView: PaperlessSavedView) {
    this.savedViewService.delete(savedView).subscribe(() => {
      this.savedViewGroup.removeControl(savedView.id.toString())
      this.savedViews.splice(this.savedViews.indexOf(savedView), 1)
      this.toastService.showInfo($localize`Saved view "${savedView.name}" deleted.`)
    })
  }

  private saveLocalSettings() {
    this.settings.set(SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE, this.settingsForm.value.bulkEditApplyOnClose)
    this.settings.set(SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS, this.settingsForm.value.bulkEditConfirmationDialogs)
    this.settings.set(SETTINGS_KEYS.DOCUMENT_LIST_SIZE, this.settingsForm.value.documentListItemPerPage)
    this.settings.set(SETTINGS_KEYS.DARK_MODE_USE_SYSTEM, this.settingsForm.value.darkModeUseSystem)
    this.settings.set(SETTINGS_KEYS.DARK_MODE_ENABLED, (this.settingsForm.value.darkModeEnabled == true).toString())
    this.settings.set(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED, (this.settingsForm.value.darkModeInvertThumbs == true).toString())
    this.settings.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, this.settingsForm.value.useNativePdfViewer)
    this.settings.set(SETTINGS_KEYS.DATE_LOCALE, this.settingsForm.value.dateLocale)
    this.settings.set(SETTINGS_KEYS.DATE_FORMAT, this.settingsForm.value.dateFormat)
    this.settings.set(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT, this.settingsForm.value.notificationsConsumerNewDocument)
    this.settings.set(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS, this.settingsForm.value.notificationsConsumerSuccess)
    this.settings.set(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED, this.settingsForm.value.notificationsConsumerFailed)
    this.settings.set(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD, this.settingsForm.value.notificationsConsumerSuppressOnDashboard)
    this.settings.setLanguage(this.settingsForm.value.displayLanguage)
    this.documentListViewService.updatePageSize()
    this.settings.updateDarkModeSettings()
    this.toastService.showInfo($localize`Settings saved successfully.`)
  }

  get displayLanguageOptions(): LanguageOption[] {
    return [
      {code: "", name: $localize`Use system language`}
    ].concat(this.settings.getLanguageOptions())
  }

  get dateLocaleOptions(): LanguageOption[] {
    return [
      {code: "", name: $localize`Use date format of display language`}
    ].concat(this.settings.getDateLocaleOptions())
  }

  get today() {
    return new Date()
  }

  saveSettings() {
    let x = []
    for (let id in this.savedViewGroup.value) {
      x.push(this.savedViewGroup.value[id])
    }
    if (x.length > 0) {
      this.savedViewService.patchMany(x).subscribe(s => {
        this.saveLocalSettings()
      }, error => {
        this.toastService.showError($localize`Error while storing settings on server: ${JSON.stringify(error.error)}`)
      })
    } else {
      this.saveLocalSettings()
    }

  }
}
