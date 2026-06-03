namespace ProposalAgent.Core;

public sealed class PeopleRoster
{
    public IReadOnlyList<PersonProfile> LoadYaml(string path)
    {
        if (!File.Exists(path))
        {
            return [];
        }

        var people = new List<PersonProfile>();
        var current = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var lists = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        string? activeList = null;

        foreach (var rawLine in File.ReadAllLines(path))
        {
            var trimmed = rawLine.Trim();
            if (trimmed.Length == 0 || trimmed == "people:")
            {
                continue;
            }

            if (trimmed.StartsWith("- name:", StringComparison.Ordinal))
            {
                AddCurrent(people, current, lists);
                current = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["name"] = Unquote(trimmed["- name:".Length..].Trim()),
                };
                lists = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
                activeList = null;
                continue;
            }

            if (trimmed.StartsWith("- ", StringComparison.Ordinal) && activeList is not null)
            {
                lists.GetValueOrDefault(activeList)?.Add(Unquote(trimmed[2..].Trim()));
                continue;
            }

            var separator = trimmed.IndexOf(':');
            if (separator <= 0)
            {
                continue;
            }

            var key = trimmed[..separator].Trim();
            var value = trimmed[(separator + 1)..].Trim();
            if (value.Length == 0)
            {
                activeList = key;
                lists.TryAdd(activeList, []);
            }
            else
            {
                activeList = null;
                current[key] = Unquote(value);
            }
        }

        AddCurrent(people, current, lists);
        return people;
    }

    private static void AddCurrent(
        List<PersonProfile> people,
        IReadOnlyDictionary<string, string> current,
        IReadOnlyDictionary<string, List<string>> lists)
    {
        if (!current.TryGetValue("name", out var name) || string.IsNullOrWhiteSpace(name))
        {
            return;
        }

        people.Add(new PersonProfile
        {
            Name = name,
            Role = current.GetValueOrDefault("role", ""),
            Company = current.GetValueOrDefault("company", ""),
            Region = current.GetValueOrDefault("region", ""),
            Office = current.GetValueOrDefault("office", ""),
            OperatingCentre = current.GetValueOrDefault("operating_centre", ""),
            Seniority = current.GetValueOrDefault("seniority", ""),
            CanLeadProposals = bool.TryParse(current.GetValueOrDefault("can_lead_proposals", ""), out var canLead) && canLead,
            Skills = lists.GetValueOrDefault("skills") ?? [],
            Industries = lists.GetValueOrDefault("industries") ?? [],
            PastProjects = lists.GetValueOrDefault("past_projects") ?? [],
            ClientRelationships = lists.GetValueOrDefault("client_relationships") ?? [],
            Availability = current.GetValueOrDefault("availability", "unknown"),
        });
    }

    private static string Unquote(string value) => value.Trim().Trim('"').Trim('\'');
}
