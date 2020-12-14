import { Component, OnInit } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { Title } from '@angular/platform-browser';
import { map, tap } from 'rxjs/operators';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { GENERAL_SETTINGS } from 'src/app/data/storage-keys';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { environment } from 'src/environments/environment';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss']
})
export class SettingsComponent implements OnInit {

  settingsForm = new FormGroup({
    'documentListItemPerPage': new FormControl(+localStorage.getItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE) || GENERAL_SETTINGS.DOCUMENT_LIST_SIZE_DEFAULT)
  })

  constructor(
    public savedViewService: SavedViewService,
    private documentListViewService: DocumentListViewService,
    private titleService: Title
  ) { }

  ngOnInit(): void {
    this.titleService.setTitle(`Settings - ${environment.appTitle}`)
  }

  deleteSavedView(savedView: PaperlessSavedView) {
    this.savedViewService.delete(savedView).subscribe(() => {})
  }

  saveSettings() {
    localStorage.setItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE, this.settingsForm.value.documentListItemPerPage)
    this.documentListViewService.updatePageSize()
  }
}
