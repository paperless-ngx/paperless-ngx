import { Pipe, PipeTransform } from '@angular/core';
import { SelectableItem } from 'src/app/components/common/filterable-dropdown/filterable-dropdown.component';

@Pipe({
  name: 'filter'
})
export class FilterPipe implements PipeTransform {
  transform(selectableItems: SelectableItem[], searchText: string): any[] {
    if (!selectableItems) return [];
    if (!searchText) return selectableItems;

    return selectableItems.filter(selectableItem => {
      return Object.keys(selectableItem.item).some(key => {
        return String(selectableItem.item[key]).toLowerCase().includes(searchText.toLowerCase());
      });
    });
   }
}
