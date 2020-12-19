import { MatchingModel } from './matching-model';
import { ObjectWithId } from './object-with-id';


export const TAG_COLOURS = [
    {id: 1, value: "#a6cee3", name: "Light Blue", textColor: "#000000"},
    {id: 2, value: "#1f78b4", name: "Blue", textColor: "#ffffff"},
    {id: 3, value: "#b2df8a", name: "Light Green", textColor: "#000000"},
    {id: 4, value: "#33a02c", name: "Green", textColor: "#000000"},
    {id: 5, value: "#fb9a99", name: "Light Red", textColor: "#000000"},
    {id: 6, value: "#e31a1c", name: "Red ", textColor: "#ffffff"},
    {id: 7, value: "#fdbf6f", name: "Light Orange", textColor: "#000000"},
    {id: 8, value: "#ff7f00", name: "Orange", textColor: "#000000"},
    {id: 9, value: "#cab2d6", name: "Light Violet", textColor: "#000000"},
    {id: 10, value: "#6a3d9a", name: "Violet", textColor: "#ffffff"},
    {id: 11, value: "#b15928", name: "Brown", textColor: "#000000"},
    {id: 12, value: "#000000", name: "Black", textColor: "#ffffff"},
    {id: 13, value: "#cccccc", name: "Light Grey", textColor: "#000000"}
]

export interface PaperlessTag extends MatchingModel {

    colour?: number

    is_inbox_tag?: boolean
  
    document_count?: number
}
