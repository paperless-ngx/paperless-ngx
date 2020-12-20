import { Pipe, PipeTransform } from '@angular/core';
import { ToggleableItem } from 'src/app/components/common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component';

@Pipe({
  name: 'filter'
})
export class FilterPipe implements PipeTransform {
  transform(toggleableItems: ToggleableItem[], searchText: string): any[] {
    if (!toggleableItems) return [];
    if (!searchText) return toggleableItems;

    return toggleableItems.filter(toggleableItem => {
      return Object.keys(toggleableItem.item).some(key => {
        return String(toggleableItem.item[key]).toLowerCase().includes(searchText.toLowerCase());
      });
    });
   }
}
