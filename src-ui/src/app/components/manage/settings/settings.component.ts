import { Component, OnInit } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { GENERAL_SETTINGS } from 'src/app/data/storage-keys';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss']
})
export class SettingsComponent implements OnInit {

  savedViewGroup = new FormGroup({})

  settingsForm = new FormGroup({
    'documentListItemPerPage': new FormControl(+localStorage.getItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE) || GENERAL_SETTINGS.DOCUMENT_LIST_SIZE_DEFAULT),
    'savedViews': this.savedViewGroup
  })

  constructor(
    public savedViewService: SavedViewService,
    private documentListViewService: DocumentListViewService,
    private toastService: ToastService
  ) { }

  savedViews: PaperlessSavedView[]

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
      this.toastService.showInfo($localize`Saved view "${savedView.name} deleted.`)
    })
  }

  private saveLocalSettings() {
    localStorage.setItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE, this.settingsForm.value.documentListItemPerPage)
    this.documentListViewService.updatePageSize()
    this.toastService.showInfo($localize`Settings saved successfully.`)
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
