import { MatchingModel } from './matching-model';
import { ObjectWithId } from './object-with-id';


export const TAG_COLOURS = [
    {id: 1, value: "#a6cee3", name: $localize`Light blue`, textColor: "#000000"},
    {id: 2, value: "#1f78b4", name: $localize`Blue`, textColor: "#ffffff"},
    {id: 3, value: "#b2df8a", name: $localize`Light green`, textColor: "#000000"},
    {id: 4, value: "#33a02c", name: $localize`Green`, textColor: "#ffffff"},
    {id: 5, value: "#fb9a99", name: $localize`Light red`, textColor: "#000000"},
    {id: 6, value: "#e31a1c", name: $localize`Red `, textColor: "#ffffff"},
    {id: 7, value: "#fdbf6f", name: $localize`Light orange`, textColor: "#000000"},
    {id: 8, value: "#ff7f00", name: $localize`Orange`, textColor: "#000000"},
    {id: 9, value: "#cab2d6", name: $localize`Light violet`, textColor: "#000000"},
    {id: 10, value: "#6a3d9a", name: $localize`Violet`, textColor: "#ffffff"},
    {id: 11, value: "#b15928", name: $localize`Brown`, textColor: "#ffffff"},
    {id: 12, value: "#000000", name: $localize`Black`, textColor: "#ffffff"},
    {id: 13, value: "#cccccc", name: $localize`Light grey`, textColor: "#000000"}
]

export interface PaperlessTag extends MatchingModel {

    colour?: number

    is_inbox_tag?: boolean
  
    document_count?: number
}
