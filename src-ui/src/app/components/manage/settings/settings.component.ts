import { Component, OnInit } from '@angular/core';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.css']
})
export class SettingsComponent implements OnInit {

  constructor(
    private savedViewConfigService: SavedViewConfigService
  ) { }

  active

  ngOnInit(): void {
  }

  deleteViewConfig(config: SavedViewConfig) {
    this.savedViewConfigService.deleteConfig(config)
  }

}
