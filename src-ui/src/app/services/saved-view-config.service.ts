import { Injectable } from '@angular/core';
import { v4 as uuidv4 } from 'uuid';
import { SavedViewConfig } from '../data/saved-view-config';

@Injectable({
  providedIn: 'root'
})
export class SavedViewConfigService {

  constructor() { 
    let savedConfigs = localStorage.getItem('saved-view-config-service:savedConfigs')
    if (savedConfigs) {
      try {
        this.configs = JSON.parse(savedConfigs)
      } catch (e) {
        this.configs = []
      }
    }
  }

  private configs: SavedViewConfig[] = []

  getConfigs(): SavedViewConfig[] {
    return this.configs
  }

  getDashboardConfigs(): SavedViewConfig[] {
    return this.configs.filter(sf => sf.showInDashboard)
  }

  getSideBarConfigs(): SavedViewConfig[] {
    return this.configs.filter(sf => sf.showInSideBar)
  }

  getConfig(id: string): SavedViewConfig {
    return this.configs.find(sf => sf.id == id)
  }

  saveConfig(config: SavedViewConfig) {
    config.id = uuidv4()
    this.configs.push(config)

    this.save()
  }

  private save() {
    localStorage.setItem('saved-view-config-service:savedConfigs', JSON.stringify(this.configs))
  }

  deleteConfig(config: SavedViewConfig) {
    let index = this.configs.findIndex(vc => vc.id == config.id)
    if (index != -1) {
      this.configs.splice(index, 1)
      this.save()
    }

  }
}
