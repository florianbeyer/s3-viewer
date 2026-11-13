from s3viewer.clipboard import CopiedObject, paste_pairs


def test_paste_puts_a_file_into_the_open_folder():
    item = CopiedObject("projekt", "readme.txt", "readme.txt", False)
    assert paste_pairs(item, "archiv/", []) == [("projekt", "readme.txt", "archiv/readme.txt")]


def test_paste_keeps_a_folder_name_and_its_contents():
    item = CopiedObject("projekt", "daten/bilder/", "bilder", True)
    pairs = paste_pairs(item, "archiv/", ["daten/bilder/a.jpg", "daten/bilder/"])
    assert set(pairs) == {
        ("projekt", "daten/bilder/a.jpg", "archiv/bilder/a.jpg"),
        ("projekt", "daten/bilder/", "archiv/bilder/"),
    }
